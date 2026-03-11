from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_SAFE_USER_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class ConversationStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def list_chats(self, user_id: str) -> list[dict[str, Any]]:
        payload = self._read_user_payload(user_id)
        chats = payload.get("chats")
        if not isinstance(chats, list):
            return []
        return [item for item in chats if isinstance(item, dict)]

    def save_chats(self, user_id: str, chats: list[dict[str, Any]]) -> None:
        normalized_chats = [item for item in chats if isinstance(item, dict)]
        payload = {
            "user_id": str(user_id or "").strip() or "browser-user",
            "chats": normalized_chats,
        }
        self._write_user_payload(user_id, payload)

    def get_chat(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
    ) -> dict[str, Any] | None:
        normalized_id = str(conversation_id or "").strip()
        if not normalized_id:
            return None
        for chat in self.list_chats(user_id):
            if str(chat.get("id") or "").strip() == normalized_id:
                return chat
        return None

    def conversation_history(
        self,
        *,
        user_id: str,
        conversation_id: str | None,
        limit: int = 8,
    ) -> list[dict[str, str]]:
        chat = self.get_chat(user_id=user_id, conversation_id=conversation_id)
        if chat is None:
            return []

        messages = chat.get("messages")
        if not isinstance(messages, list):
            return []

        history: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = str(message.get("role") or "").strip()
            text = str(message.get("text") or "").strip()
            if role not in {"user", "assistant"} or not text:
                continue
            if role == "assistant" and bool(message.get("streaming")):
                continue
            history.append({"role": role, "text": text})

        if limit > 0:
            return history[-limit:]
        return history

    def _user_file(self, user_id: str) -> Path:
        normalized_user = _SAFE_USER_PATTERN.sub(
            "_",
            str(user_id or "").strip() or "browser-user",
        ).strip("._-")
        if not normalized_user:
            normalized_user = "browser-user"
        return self.root / "{user_id}.json".format(user_id=normalized_user)

    def _read_user_payload(self, user_id: str) -> dict[str, Any]:
        path = self._user_file(user_id)
        if not path.exists():
            return {"user_id": str(user_id or "").strip() or "browser-user", "chats": []}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"user_id": str(user_id or "").strip() or "browser-user", "chats": []}
        return payload if isinstance(payload, dict) else {"user_id": str(user_id or "").strip() or "browser-user", "chats": []}

    def _write_user_payload(self, user_id: str, payload: dict[str, Any]) -> None:
        path = self._user_file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix("{suffix}.tmp".format(suffix=path.suffix))
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(path)
