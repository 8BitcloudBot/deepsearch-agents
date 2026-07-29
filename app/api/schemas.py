"""Phase 2 HTTP request/response and WebSocket message schemas."""

from typing import Literal

from pydantic import BaseModel, Field

# ── Task ─────────────────────────────────────────────────────────────────────


class TaskStartRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)


class TaskStartResponse(BaseModel):
    thread_id: str
    status: Literal["accepted"] = "accepted"


class TaskCancelResponse(BaseModel):
    thread_id: str
    status: Literal["cancelled", "cancelling", "not_found"]


# ── Upload ───────────────────────────────────────────────────────────────────


class UploadResponse(BaseModel):
    filename: str
    size: int


# ── Files / Download ─────────────────────────────────────────────────────────


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    media_type: str


class FileListResponse(BaseModel):
    files: list[FileInfo]


# ── WebSocket messages ───────────────────────────────────────────────────────


class HeartbeatMessage(BaseModel):
    type: Literal["pong"]


class ErrorMessage(BaseModel):
    type: Literal["error"]
    detail: str
