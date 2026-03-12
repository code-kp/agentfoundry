from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Sequence

from core.retrieval.index import LocalEmbeddingIndex
from core.retrieval.scoring import stable_fingerprint
from core.retrieval.service import SemanticRetriever
from core.retrieval.types import DirtyIndexStatus, RetrievalDocument, RetrievalMatch


_SUMMARY_HINT_PHRASES = (
    "what have we discussed",
    "what did we discuss",
    "what have we talked about",
    "what did we talk about",
    "what have we been talking about",
    "catch me up",
    "sum up",
)
_CURRENT_CONVERSATION_HINT_PHRASES = (
    "this chat",
    "this conversation",
    "this thread",
    "this session",
    "our chat",
    "our conversation",
    "our thread",
    "our session",
    "current chat",
    "current conversation",
    "so far",
    "up to now",
    "thus far",
)
_SUMMARY_TOKENS = {
    "summarize",
    "summary",
    "summarise",
    "recap",
    "brief",
    "overview",
}
_CONVERSATION_TOKENS = {
    "chat",
    "conversation",
    "thread",
    "session",
    "discussion",
}
_QUERY_STOPWORDS = {
    "a",
    "an",
    "the",
    "this",
    "that",
    "our",
    "my",
    "me",
    "we",
    "us",
    "please",
    "can",
    "could",
    "would",
    "you",
    "give",
    "provide",
    "for",
    "of",
    "to",
    "from",
    "in",
    "on",
    "about",
    "so",
    "far",
    "now",
    "current",
}


class ConversationCorpusBuilder:
    def __init__(
        self,
        conversations_root: Path,
        *,
        window_size: int = 4,
        window_step: int = 2,
    ) -> None:
        self.conversations_root = conversations_root
        self.window_size = max(int(window_size or 2), 2)
        self.window_step = max(int(window_step or 1), 1)

    def list_user_ids(self) -> list[str]:
        if not self.conversations_root.exists():
            return []
        return sorted(path.stem for path in self.conversations_root.glob("*.json"))

    def build_documents(self, *, user_id: str) -> list[RetrievalDocument]:
        payload = self._read_user_payload(user_id)
        chats = payload.get("chats")
        if not isinstance(chats, list):
            return []

        documents: list[RetrievalDocument] = []
        for chat in chats:
            if not isinstance(chat, dict):
                continue
            documents.extend(self._build_chat_documents(user_id=user_id, chat=chat))
        return documents

    def build_all_documents(self, *, user_id: str | None = None) -> list[RetrievalDocument]:
        if user_id:
            return self.build_documents(user_id=user_id)

        documents: list[RetrievalDocument] = []
        for discovered_user_id in self.list_user_ids():
            documents.extend(self.build_documents(user_id=discovered_user_id))
        return documents

    def _build_chat_documents(
        self,
        *,
        user_id: str,
        chat: dict[str, Any],
    ) -> list[RetrievalDocument]:
        conversation_id = str(chat.get("id") or "").strip()
        if not conversation_id:
            return []

        title = str(chat.get("title") or "Conversation").strip() or "Conversation"
        agent_id = str(chat.get("agentId") or "").strip()
        updated_at = int(chat.get("updatedAt") or 0)
        messages = self._normalize_messages(chat.get("messages"))
        if not messages:
            return []

        windows = _windowed_messages(
            messages,
            window_size=self.window_size,
            window_step=self.window_step,
        )
        documents: list[RetrievalDocument] = []
        total_messages = len(messages)
        for start_index, end_index, window in windows:
            lines = [
                "Conversation title: {title}".format(title=title),
            ]
            if agent_id:
                lines.append("Agent: {agent_id}".format(agent_id=agent_id))
            lines.extend(
                "{role}: {text}".format(role=item["role"], text=item["text"])
                for item in window
            )
            text = "\n".join(lines)
            doc_id = "conversation::{user_id}::{conversation_id}::{start}:{end}".format(
                user_id=user_id,
                conversation_id=conversation_id,
                start=start_index,
                end=end_index,
            )
            documents.append(
                RetrievalDocument(
                    corpus="conversations",
                    doc_id=doc_id,
                    source_id="{user_id}:{conversation_id}".format(
                        user_id=user_id,
                        conversation_id=conversation_id,
                    ),
                    text=text,
                    fingerprint=stable_fingerprint(
                        user_id,
                        conversation_id,
                        title,
                        agent_id,
                        str(start_index),
                        str(end_index),
                        text,
                    ),
                    metadata={
                        "user_id": user_id,
                        "conversation_id": conversation_id,
                        "agent_id": agent_id,
                        "title": title,
                        "updated_at": updated_at,
                        "window_start": start_index,
                        "window_end": end_index,
                        "total_messages": total_messages,
                    },
                )
            )
        return documents

    def _normalize_messages(self, messages: Any) -> list[dict[str, str]]:
        if not isinstance(messages, list):
            return []

        normalized: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip()
            text = str(message.get("text") or "").strip()
            if role not in {"user", "assistant"} or not text:
                continue
            if role == "assistant" and bool(message.get("streaming")):
                continue
            normalized.append({"role": role, "text": text})
        return normalized

    def _read_user_payload(self, user_id: str) -> dict[str, Any]:
        path = self.conversations_root / "{user_id}.json".format(user_id=user_id)
        if not path.exists():
            return {"user_id": user_id, "chats": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"user_id": user_id, "chats": []}
        return payload if isinstance(payload, dict) else {"user_id": user_id, "chats": []}


class ConversationSemanticRetriever:
    def __init__(
        self,
        *,
        conversations_root: Path,
        embeddings_root: Path,
    ) -> None:
        self.builder = ConversationCorpusBuilder(conversations_root)
        self.retriever = SemanticRetriever(LocalEmbeddingIndex(embeddings_root))

    def dirty_status(self, *, user_id: str | None = None) -> DirtyIndexStatus:
        documents = self.builder.build_all_documents(user_id=user_id)
        return self.retriever.dirty_status("conversations", documents)

    def sync(
        self,
        *,
        user_id: str | None = None,
        full_rebuild: bool = False,
    ) -> DirtyIndexStatus:
        documents = self.builder.build_all_documents(user_id=user_id)
        return self.retriever.sync_documents(
            "conversations",
            documents,
            full_rebuild=full_rebuild,
        )

    def recall(
        self,
        *,
        query: str,
        user_id: str,
        conversation_id: str | None,
        agent_id: str,
        history: Sequence[dict[str, str]] | None,
        max_results: int = 3,
        query_vector: Sequence[float] | None = None,
    ) -> tuple[list[RetrievalMatch], DirtyIndexStatus]:
        documents = self.builder.build_documents(user_id=user_id)
        history_count = len(list(history or []))
        normalized_conversation_id = str(conversation_id or "").strip()
        same_conversation_only = bool(normalized_conversation_id) and _targets_current_conversation(
            query
        )

        def document_filter(document: RetrievalDocument) -> bool:
            metadata = document.metadata
            if str(metadata.get("user_id") or "").strip() != str(user_id or "").strip():
                return False
            if not normalized_conversation_id:
                return True

            doc_conversation_id = str(metadata.get("conversation_id") or "").strip()
            if same_conversation_only:
                if doc_conversation_id != normalized_conversation_id:
                    return False
            elif doc_conversation_id != normalized_conversation_id:
                return True

            total_messages = int(metadata.get("total_messages") or 0)
            window_end = int(metadata.get("window_end") or -1)
            cutoff = max(total_messages - history_count, 0)
            return history_count <= 0 or window_end < cutoff

        def metadata_boost(
            document: RetrievalDocument,
            _query_tokens: tuple[str, ...],
        ) -> float:
            metadata = document.metadata
            boost = 0.0
            if (
                normalized_conversation_id
                and str(metadata.get("conversation_id") or "").strip()
                == normalized_conversation_id
            ):
                boost += 0.15
            if agent_id and str(metadata.get("agent_id") or "").strip() == agent_id:
                boost += 0.05

            total_messages = int(metadata.get("total_messages") or 0)
            window_end = int(metadata.get("window_end") or 0)
            if total_messages > 0:
                boost += min(window_end / total_messages, 1.0) * 0.05
            return boost

        try:
            return self.retriever.search(
                "conversations",
                documents,
                query=query,
                max_results=max_results,
                metadata_boost=metadata_boost,
                document_filter=document_filter,
                query_vector=query_vector,
            )
        except Exception:
            return [], self.retriever.dirty_status("conversations", documents)


def _targets_current_conversation(query: str) -> bool:
    normalized = " ".join(str(query or "").lower().split())
    if not normalized:
        return False

    if any(phrase in normalized for phrase in _SUMMARY_HINT_PHRASES):
        return True

    tokens = re.findall(r"[a-z0-9']+", normalized)
    if not tokens:
        return False

    has_summary_token = any(token in _SUMMARY_TOKENS for token in tokens)
    has_conversation_token = any(token in _CONVERSATION_TOKENS for token in tokens)
    if not has_summary_token:
        return False

    if any(phrase in normalized for phrase in _CURRENT_CONVERSATION_HINT_PHRASES):
        return True

    content_tokens = [
        token
        for token in tokens
        if token not in _QUERY_STOPWORDS
        and token not in _SUMMARY_TOKENS
        and token not in _CONVERSATION_TOKENS
    ]
    return has_conversation_token and not content_tokens


def _windowed_messages(
    messages: Sequence[dict[str, str]],
    *,
    window_size: int,
    window_step: int,
) -> list[tuple[int, int, Sequence[dict[str, str]]]]:
    if not messages:
        return []
    if len(messages) <= window_size:
        return [(0, len(messages), messages)]

    windows: list[tuple[int, int, Sequence[dict[str, str]]]] = []
    last_index = len(messages) - window_size
    for start_index in range(0, last_index + 1, window_step):
        end_index = min(start_index + window_size, len(messages))
        windows.append((start_index, end_index, messages[start_index:end_index]))

    final_start = max(len(messages) - window_size, 0)
    final_window = (final_start, len(messages), messages[final_start:])
    if not windows or windows[-1][0] != final_window[0]:
        windows.append(final_window)
    return windows
