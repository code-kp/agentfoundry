from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from agent_foundry.api import AgentApi
from agent_foundry.http_models import AiRequest, ChatRequest, ConversationsRequest
from core.execution.shared.request_context import (
    bind_conversation_id,
    reset_conversation_id,
)
from core.platform import AgentPlatform
from services.ai import AiService, AiServiceError
from services.conversations import ConversationStore


@dataclass(frozen=True)
class ServerServices:
    platform_service: AgentPlatform
    service: AgentApi
    ai_service: AiService
    conversation_store: ConversationStore


def build_api_router(services: ServerServices) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    async def health() -> JSONResponse:
        return JSONResponse({"ok": True})

    @router.get("/api/agents")
    async def agents() -> JSONResponse:
        return JSONResponse(services.service.catalog())

    @router.get("/api/models")
    async def models() -> JSONResponse:
        return JSONResponse(services.service.list_available_models())

    @router.get("/api/conversations")
    async def conversations(user_id: str = "browser-user") -> JSONResponse:
        return JSONResponse({"chats": services.conversation_store.list_chats(user_id)})

    @router.get("/api/conversations/session")
    async def conversation_session(
        user_id: str = "browser-user",
        conversation_id: str = "",
        agent_id: str = "",
        mode: Optional[str] = None,
        model_id: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> JSONResponse:
        normalized_conversation_id = conversation_id.strip()
        normalized_agent_id = agent_id.strip()
        if not normalized_conversation_id or not normalized_agent_id:
            return JSONResponse({"session_id": None})

        selected_model_name, resolved_agent_id, resolved_mode = (
            _resolve_runtime_selection(
                services,
                agent_id=normalized_agent_id,
                mode=mode,
                model_id=model_id,
                model_name=model_name,
            )
        )

        return JSONResponse(
            {
                "session_id": services.conversation_store.session_id(
                    user_id=user_id,
                    conversation_id=normalized_conversation_id,
                    agent_id=resolved_agent_id,
                    mode=resolved_mode,
                    model_name=selected_model_name,
                )
            }
        )

    @router.put("/api/conversations")
    async def save_conversations(payload: ConversationsRequest) -> JSONResponse:
        services.conversation_store.save_chats(payload.user_id, payload.chats)
        return JSONResponse({"ok": True})

    @router.post("/api/chat/stream")
    async def stream_chat(payload: ChatRequest) -> StreamingResponse:
        try:
            (
                selected_model_name,
                resolved_agent_id,
                resolved_mode,
            ) = _resolve_runtime_selection(
                services,
                agent_id=payload.agent_id,
                mode=payload.mode,
                model_id=payload.model_id,
                model_name=payload.model_name,
            )
            stored_history = services.conversation_store.conversation_history(
                user_id=payload.user_id,
                conversation_id=payload.conversation_id,
            )
            stored_session_id = (
                payload.session_id
                or services.conversation_store.session_id(
                    user_id=payload.user_id,
                    conversation_id=payload.conversation_id,
                    agent_id=resolved_agent_id,
                    mode=resolved_mode,
                    model_name=selected_model_name,
                )
            )
            request_history = (
                [item.model_dump() for item in payload.history]
                if payload.history
                else None
            )
            conversation_token = bind_conversation_id(payload.conversation_id)
            try:
                agent_id, mode, session_id, stream = await services.service.stream_chat(
                    agent_id=payload.agent_id,
                    team_agent_ids=payload.team_agent_ids,
                    mode=payload.mode,
                    model_name=selected_model_name,
                    message=payload.message,
                    user_id=payload.user_id,
                    session_id=stored_session_id,
                    history=stored_history or request_history,
                    stream=payload.stream,
                )
            finally:
                reset_conversation_id(conversation_token)
            services.conversation_store.save_session_id(
                user_id=payload.user_id,
                conversation_id=payload.conversation_id,
                agent_id=agent_id,
                mode=mode,
                model_name=selected_model_name,
                session_id=session_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        headers = {
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Agent-Id": agent_id,
            "X-Mode": mode,
            "X-Session-Id": session_id,
        }
        return StreamingResponse(
            stream, media_type="text/event-stream", headers=headers
        )

    @router.post("/api/ai")
    async def run_ai_request(payload: AiRequest) -> JSONResponse:
        try:
            selected_model_name = services.service.resolve_model_name(
                model_id=payload.model_id,
                model_name=payload.model_name,
            )
            text = await services.ai_service.generate_text(
                agent_id=payload.agent_id,
                model_name=selected_model_name,
                instructions=payload.instructions,
                message=payload.message,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except AiServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return JSONResponse({"text": text})

    @router.post("/api/skills/upload")
    async def upload_skill(
        file: UploadFile = File(...),
        user_id: str = Form("browser-user"),
        namespace: str = Form(""),
    ) -> JSONResponse:
        file_name = (file.filename or "").strip()
        if not file_name:
            raise HTTPException(
                status_code=400, detail="Uploaded file is missing a filename."
            )
        if not file_name.lower().endswith(".md"):
            raise HTTPException(
                status_code=400, detail="Only markdown (.md) files are supported."
            )

        raw_content = await file.read()
        try:
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=400, detail="Uploaded markdown must be valid UTF-8."
            ) from exc

        try:
            uploaded = services.service.upload_skill_markdown(
                file_name=file_name,
                content=content,
                uploader_id=user_id,
                namespace=namespace,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return JSONResponse(
            {
                "skill": uploaded,
                "usage": {
                    "note": (
                        "Uploaded markdown is treated as user-scoped knowledge. "
                        "It is available across all agents for the same user id."
                    ),
                },
            }
        )

    return router


def _resolve_runtime_selection(
    services: ServerServices,
    *,
    agent_id: Optional[str],
    mode: Optional[str],
    model_id: Optional[str],
    model_name: Optional[str],
) -> tuple[Optional[str], str, str]:
    try:
        selected_model_name = services.service.resolve_model_name(
            model_id=model_id,
            model_name=model_name,
        )
        resolved_agent_id, resolved_mode, _runtime = (
            services.platform_service.resolve_runtime(
                agent_id,
                mode=mode,
                model_name=selected_model_name,
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return selected_model_name, resolved_agent_id, resolved_mode
