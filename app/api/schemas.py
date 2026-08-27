"""Public HTTP schemas for the schema 5.0 conversation product."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: str
    username: str
    role: Literal["admin", "user"]


class AdminUserResponse(UserResponse):
    conversation_count: int


class LoginResponse(BaseModel):
    user: UserResponse


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="新研究", min_length=1, max_length=120)


class ConversationRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)


class TurnStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=10000)
    use_web: StrictBool = False


class AttachmentResponse(BaseModel):
    id: str
    name: str
    size: int
    media_type: str
    active: bool


class TurnResponse(BaseModel):
    id: str
    question: str
    answer: str | None
    use_web: bool
    status: str
    attachment_ids: list[str]
    result: dict[str, Any] | None
    created_at: str
    completed_at: str | None


class ConversationResponse(BaseModel):
    id: str
    title: str
    owner_id: str
    created_at: str
    updated_at: str
    turns: list[TurnResponse] = Field(default_factory=list)
    attachments: list[AttachmentResponse] = Field(default_factory=list)


class TurnStartResponse(BaseModel):
    status: Literal["started"] = "started"
    turn_id: str
    conversation_id: str
    use_web: bool


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "deepsearch-conversation"
    schema_version: Literal["5.0.0"] = "5.0.0"
    capabilities: dict[str, dict[str, str]]


class LibraryDocument(BaseModel):
    document_id: str
    name: str
    chunks: int
