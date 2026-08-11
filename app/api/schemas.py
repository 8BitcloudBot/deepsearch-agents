"""Phase 2 HTTP request/response and WebSocket message schemas."""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


# ── Task ─────────────────────────────────────────────────────────────────────


class TaskStartRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    thread_id: str | None = None

    @field_validator("thread_id")
    @classmethod
    def _validate_thread_id(cls, v: str | None) -> str | None:
        if v is not None and not UUID_RE.fullmatch(v):
            raise ValueError(f"thread_id must be a UUID, got {v!r}")
        return v


class TaskStartResponse(BaseModel):
    status: Literal["started"] = "started"
    thread_id: str


class TaskCancelResponse(BaseModel):
    thread_id: str
    status: Literal["cancelled", "cancelling", "not_found"]


# ── Upload ───────────────────────────────────────────────────────────────────


class UploadFileInfo(BaseModel):
    name: str
    size: int


class UploadResponse(BaseModel):
    status: Literal["uploaded"] = "uploaded"
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


# ── Citations ────────────────────────────────────────────────────────────────


class CitationsResponse(BaseModel):
    """Validated citation results attached to one thread (P4-5).

    ``report`` is the versioned P4-4 evaluation report dict: schema version,
    provenance bound to the frozen manifests, the three homogeneous
    partitions, and the report fingerprint.
    """

    thread_id: str
    report: dict[str, Any]


class LiveCitationsResponse(BaseModel):
    """Thread-scoped live citation delivery document (P4.5-4)."""

    thread_id: str
    document: dict[str, Any]


# ── WebSocket messages ───────────────────────────────────────────────────────


class HeartbeatMessage(BaseModel):
    type: Literal["pong"] = "pong"
