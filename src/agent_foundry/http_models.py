from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: str
    text: str


class ChatRequest(BaseModel):
    message: str
    agent_id: Optional[str] = None
    team_agent_ids: Optional[List[str]] = None
    mode: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: str = "browser-user"
    history: Optional[List[HistoryMessage]] = None
    stream: bool = True


class AiRequest(BaseModel):
    agent_id: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    instructions: str
    message: str


class ConversationsRequest(BaseModel):
    user_id: str = "browser-user"
    chats: List[dict[str, Any]] = Field(default_factory=list)
