"""Phase 2 HTTP request/response and WebSocket message schemas."""

from pydantic import BaseModel, Field

# ── Task ─────────────────────────────────────────────────────────────────────


class TaskStartRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None


class TaskStartResponse(BaseModel):
    status: str = "started"
    thread_id: str


class TaskCancelResponse(BaseModel):
    thread_id: str
    status: str  # "cancelled" | "cancelling" | "not_found"


# ── Upload ───────────────────────────────────────────────────────────────────


class UploadFileInfo(BaseModel):
    filename: str
    size: int
    media_type: str


class UploadResponse(BaseModel):
    status: str = "uploaded"
    thread_id: str
    files: list[UploadFileInfo]


# ── Files / Download ─────────────────────────────────────────────────────────


class FileInfo(BaseModel):
    name: str
    path: str
    size: int
    media_type: str


class FileListResponse(BaseModel):
    thread_id: str
    files: list[FileInfo]


# ── WebSocket messages ───────────────────────────────────────────────────────


class HeartbeatMessage(BaseModel):
    type: str = "pong"
