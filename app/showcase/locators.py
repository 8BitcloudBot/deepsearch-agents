"""Typed, deterministic locators for the P4.5-2 live-source boundary.

The module is deliberately provider-agnostic.  It canonicalizes identity and
metadata only; adapters in :mod:`app.showcase.locator_adapters` translate
provider-shaped values into these records without performing I/O.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
import re
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from app.citations.rules import redact
from app.showcase.contracts import (
    EvidencePartition,
    ExecutionMode,
    Limitation,
    RecordType,
    SourceKind,
    validate_live_source_result,
)


class LocatorError(ValueError):
    """A locator input failed closed after redaction."""

    def __init__(self, message: str):
        super().__init__(redact(message))


class LocatorState(StrEnum):
    VALID = "valid"
    STALE = "stale"
    MISSING = "missing"


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_ALIAS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]{0,63}$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_ENCODED_CONTROL_RE = re.compile(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", re.I)
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "api-key",
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
    }
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def _fail(message: str) -> None:
    raise LocatorError(message)


def _text(value: Any, field: str, *, max_length: int = 2048) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string: {value!r}")
    if len(value) > max_length or any(ord(ch) < 0x20 for ch in value):
        _fail(f"{field} is too long or contains control characters: {value!r}")
    return value.strip()


def _timestamp(value: Any) -> str:
    raw = _text(value, "captured_at", max_length=64)
    if not _TIMESTAMP_RE.fullmatch(raw):
        _fail("captured_at must be an ISO-8601 timestamp with a timezone")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LocatorError("captured_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        _fail("captured_at must include a timezone")
    return raw


def _version(value: Any) -> str:
    result = _text(value, "version", max_length=128)
    if not _SEMVER_RE.fullmatch(result):
        _fail("version must be a semantic version")
    return result


def _source_kind(value: SourceKind | str) -> SourceKind:
    try:
        return value if isinstance(value, SourceKind) else SourceKind(value)
    except ValueError as exc:
        raise LocatorError(f"unknown source kind: {value!r}") from exc


def _stable_id(kind: SourceKind, identity: str) -> str:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
    return f"src-{kind.value}-{digest}"


def _identifier(
    value: Any, field: str, *, alias: bool = False, max_length: int = 128
) -> str:
    result = _text(value, field, max_length=max_length)
    pattern = _ALIAS_RE if alias else _IDENTIFIER_RE
    if not pattern.fullmatch(result):
        _fail(f"{field} contains unsafe characters: {result!r}")
    lowered = result.casefold()
    if (
        lowered.startswith("sk-")
        or "password" in lowered
        or "secret" in lowered
        or "api_key" in lowered
        or "token" in lowered
    ):
        _fail(f"{field} contains a secret-like value")
    return result


def _json_identity(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass(frozen=True)
class WebLocator:
    canonical_url: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "canonical_url", canonicalize_web_url(self.canonical_url)
        )

    def canonical_identity(self) -> str:
        return self.canonical_url

    def as_contract(self) -> dict[str, str]:
        return {"kind": "url", "value": self.canonical_url}


@dataclass(frozen=True)
class MySQLLocator:
    connection_alias: str
    database: str
    table: str
    query_fingerprint: str
    row_identity: str
    column: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "connection_alias",
            _identifier(
                self.connection_alias,
                "connection_alias",
                alias=True,
                max_length=64,
            ),
        )
        for field in ("database", "table", "column"):
            object.__setattr__(
                self,
                field,
                _identifier(getattr(self, field), field, max_length=64),
            )
        if not re.fullmatch(r"[0-9a-f]{32}(?:[0-9a-f]{32})?", self.query_fingerprint):
            _fail("query_fingerprint must be a SHA-256 fingerprint")
        row_identity = _text(self.row_identity, "row_identity", max_length=128)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}", row_identity):
            _fail("row_identity contains unsafe characters")
        if row_identity.casefold().startswith("sk-"):
            _fail("row_identity contains a secret-like value")
        object.__setattr__(self, "row_identity", row_identity)

    def canonical_identity(self) -> str:
        return "|".join(
            (
                self.connection_alias,
                self.database,
                self.table,
                self.query_fingerprint,
                self.row_identity,
                self.column,
            )
        )

    def as_contract(self) -> dict[str, str]:
        value = ":".join(
            (
                self.connection_alias,
                self.database,
                self.table,
                self.query_fingerprint,
                self.row_identity,
                self.column,
            )
        )
        return {"kind": "row", "value": value}


@dataclass(frozen=True)
class KnowledgeChunkLocator:
    collection_id: str
    document_id: str
    chunk_id: str

    def __post_init__(self) -> None:
        for field in ("collection_id", "document_id", "chunk_id"):
            object.__setattr__(self, field, _identifier(getattr(self, field), field))

    def canonical_identity(self) -> str:
        return "|".join((self.collection_id, self.document_id, self.chunk_id))

    def as_contract(self) -> dict[str, str]:
        return {
            "kind": "chunk",
            "value": ":".join((self.collection_id, self.document_id, self.chunk_id)),
        }


@dataclass(frozen=True)
class FilePosition:
    page: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    char_start: int | None = None
    char_end: int | None = None

    def __post_init__(self) -> None:
        if all(
            value is None
            for value in (
                self.page,
                self.line_start,
                self.line_end,
                self.char_start,
                self.char_end,
            )
        ):
            _fail("file position must include at least one coordinate")
        for name in ("page", "line_start", "line_end", "char_start", "char_end"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                _fail(f"{name} must be a non-negative integer")
            if name == "page" and value is not None and value < 1:
                _fail("page must be a positive integer")
            if name in {"line_start", "line_end"} and value is not None and value < 1:
                _fail(f"{name} must be a positive integer")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            _fail("line_end must be greater than or equal to line_start")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            _fail("char_end must be greater than or equal to char_start")

    def canonical_identity(self) -> str:
        return _json_identity(
            {
                "page": self.page,
                "line_start": self.line_start,
                "line_end": self.line_end,
                "char_start": self.char_start,
                "char_end": self.char_end,
            }
        )

    def as_text(self) -> str:
        parts: list[str] = []
        if self.page is not None:
            parts.append(f"page={self.page}")
        if self.line_start is not None or self.line_end is not None:
            parts.append(f"line={self.line_start}-{self.line_end}")
        if self.char_start is not None or self.char_end is not None:
            parts.append(f"char={self.char_start}-{self.char_end}")
        return ",".join(parts)


@dataclass(frozen=True)
class UploadedFileLocator:
    thread_id: str
    artifact_name: str
    position: FilePosition

    def __post_init__(self) -> None:
        thread_id = _text(self.thread_id, "thread_id", max_length=64).lower()
        if not _UUID_RE.fullmatch(thread_id):
            _fail("thread_id must be a UUID")
        artifact = _text(self.artifact_name, "artifact_name", max_length=255)
        if (
            artifact != artifact.split("/")[-1]
            or artifact != artifact.split("\\")[-1]
            or artifact in {".", ".."}
        ):
            _fail("artifact_name must be a basename")
        object.__setattr__(self, "thread_id", thread_id)
        object.__setattr__(self, "artifact_name", artifact)

    def canonical_identity(self) -> str:
        return "|".join(
            (self.thread_id, self.artifact_name, self.position.canonical_identity())
        )

    def as_contract(self) -> dict[str, str]:
        return {
            "kind": "span",
            "value": f"{self.artifact_name}:{self.position.as_text()}",
        }


LocatorBody = WebLocator | MySQLLocator | KnowledgeChunkLocator | UploadedFileLocator


@dataclass(frozen=True)
class SourceLocator:
    source_kind: SourceKind
    title: str
    captured_at: str
    version: str
    display_text: str
    locator: LocatorBody
    thread_id: str | None = None
    state: LocatorState = LocatorState.VALID
    safe_display_link: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_kind", _source_kind(self.source_kind))
        expected_body = {
            SourceKind.WEB: WebLocator,
            SourceKind.MYSQL: MySQLLocator,
            SourceKind.KNOWLEDGE: KnowledgeChunkLocator,
            SourceKind.UPLOADED_FILE: UploadedFileLocator,
        }[self.source_kind]
        if not isinstance(self.locator, expected_body):
            _fail(f"locator body does not match source kind {self.source_kind.value!r}")
        object.__setattr__(self, "title", _text(self.title, "title", max_length=200))
        object.__setattr__(
            self,
            "display_text",
            _text(self.display_text, "display_text", max_length=2048),
        )
        object.__setattr__(self, "captured_at", _timestamp(self.captured_at))
        object.__setattr__(self, "version", _version(self.version))
        if self.thread_id is not None:
            thread_id = _text(self.thread_id, "thread_id", max_length=64).lower()
            if not _UUID_RE.fullmatch(thread_id):
                _fail("thread_id must be a UUID")
            object.__setattr__(self, "thread_id", thread_id)
        if isinstance(self.locator, UploadedFileLocator):
            if self.thread_id != self.locator.thread_id:
                _fail("uploaded locator thread scope is inconsistent")
            expected_link = (
                f"/api/threads/{self.thread_id}/uploads/"
                f"{quote(self.locator.artifact_name, safe='')}"
            )
            if self.safe_display_link != expected_link:
                _fail("uploaded locator display link is not the approved relative link")
        elif isinstance(self.locator, WebLocator):
            if self.safe_display_link != self.locator.canonical_url:
                _fail("web locator display link must be its canonical URL")
        elif self.safe_display_link is not None:
            _fail("this source kind does not permit a display link")

    @property
    def source_id(self) -> str:
        return _stable_id(self.source_kind, self.canonical_identity())

    def canonical_identity(self) -> str:
        return f"{self.source_kind.value}|{self.locator.canonical_identity()}"

    def as_contract(self) -> dict[str, str]:
        return self.locator.as_contract()

    def as_live_source_result(
        self,
        title: str | None = None,
        display_text: str | None = None,
        expected_thread_id: str | None = None,
    ) -> dict[str, Any]:
        if self.state is not LocatorState.VALID:
            _fail(f"cannot serialize {self.state.value} source locator")
        if expected_thread_id is not None and self.thread_id != expected_thread_id:
            _fail("locator thread scope does not match the expected thread")
        raw = {
            "type": RecordType.LIVE_SOURCE_RESULT.value,
            "source_id": self.source_id,
            "source_kind": self.source_kind.value,
            "title": redact(title if title is not None else self.title),
            "captured_at": self.captured_at,
            "version": self.version,
            "display_text": redact(
                display_text if display_text is not None else self.display_text
            ),
            "locator": self.as_contract(),
            "execution_mode": ExecutionMode.LIVE.value,
            "evidence_partition": EvidencePartition.LIVE.value,
        }
        return validate_live_source_result(raw)


@dataclass(frozen=True)
class LocatorResolution:
    locator: SourceLocator | None
    limitation: Limitation | None = None


def missing_resolution(
    source_kind: SourceKind | str, message: str = "source is unavailable"
) -> LocatorResolution:
    kind = _source_kind(source_kind)
    return LocatorResolution(None, Limitation("missing-source", kind, redact(message)))


def stale_resolution(
    locator: SourceLocator, message: str = "source locator is stale"
) -> LocatorResolution:
    return LocatorResolution(
        replace(locator, state=LocatorState.STALE),
        Limitation("stale-source", locator.source_kind, redact(message)),
    )


def canonicalize_web_url(url: str) -> str:
    raw = _text(url, "url", max_length=512)
    if any(
        ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw
    ) or _ENCODED_CONTROL_RE.search(raw):
        _fail("url contains control characters")
    try:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            _fail("url must use HTTP or HTTPS and include a host")
        if parts.username is not None or parts.password is not None:
            _fail("url userinfo is not allowed")
        host = parts.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        port = parts.port
    except (ValueError, UnicodeError) as exc:
        raise LocatorError("url is malformed") from exc
    scheme = parts.scheme.lower()
    netloc = host
    if ":" in host:
        netloc = f"[{host}]"
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{netloc}:{port}"
    path = parts.path or "/"
    normalized = posixpath.normpath(path)
    if path.startswith("/") and not normalized.startswith("/"):
        normalized = "/" + normalized
    if normalized == ".":
        normalized = "/"
    query_pairs = sorted(
        parse_qsl(parts.query, keep_blank_values=True),
        key=lambda item: (item[0], item[1]),
    )
    if any(key.casefold() in _SENSITIVE_QUERY_KEYS for key, _value in query_pairs):
        _fail("url contains a secret-bearing query parameter")
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((scheme, netloc, normalized, query, ""))
