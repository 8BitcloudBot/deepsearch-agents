"""Pure adapters from existing provider-shaped values to source locators."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import sqlglot

from app.citations.rules import redact
from app.providers.mysql import ReadOnlyQueryError, validate_readonly_query
from app.showcase.contracts import SourceKind
from app.showcase.locators import (
    FilePosition,
    KnowledgeChunkLocator,
    LocatorError,
    MySQLLocator,
    SourceLocator,
    UploadedFileLocator,
    WebLocator,
    _identifier,
    _text,
    _timestamp,
    _version,
    canonicalize_web_url,
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _bounded_display(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocatorError("display_text must be a non-empty string")
    normalized = re.sub(r"\s+", " ", value).strip()
    return redact(normalized)[:2048]


def _metadata(
    data: Any, captured_at: str | None, version: str | None
) -> tuple[str, str]:
    captured_value = (
        captured_at if captured_at is not None else _get(data, "captured_at")
    )
    version_value = version if version is not None else _get(data, "version")
    if captured_value is None:
        raise LocatorError("captured_at is required for a source locator")
    if version_value is None:
        raise LocatorError("version is required for a source locator")
    return _timestamp(captured_value), _version(version_value)


def normalize_tavily_hit(
    hit: Any,
    *,
    captured_at: str | None = None,
    version: str | None = None,
    thread_id: str | None = None,
) -> SourceLocator:
    """Normalize a Tavily ``SearchHit`` or JSON fixture without network access."""
    url = canonicalize_web_url(_get(hit, "url"))
    title = _text(redact(_get(hit, "title", "Web source")), "title", max_length=200)
    display_value = _get(hit, "content") or _get(hit, "raw_content", "")
    display = _bounded_display(display_value)
    captured, release = _metadata(hit, captured_at, version)
    return SourceLocator(
        SourceKind.WEB,
        title,
        captured,
        release,
        display,
        WebLocator(url),
        thread_id=thread_id,
        safe_display_link=url,
    )


def _canonical_sql(query: str, database: str) -> tuple[str, str]:
    query = _text(query, "query", max_length=8192)
    try:
        validate_readonly_query(query, database=database)
        parsed = sqlglot.parse_one(query, dialect="mysql")
        canonical = parsed.sql(dialect="mysql", normalize=True)
    except (ReadOnlyQueryError, sqlglot.errors.ParseError, ValueError) as exc:
        raise LocatorError("query is not an approved read-only query") from exc
    fingerprint = hashlib.sha256(canonical.casefold().encode("utf-8")).hexdigest()
    return canonical, fingerprint


def normalize_mysql_row(
    row: Any,
    *,
    connection_alias: str | None = None,
    database: str | None = None,
    table: str | None = None,
    query: str | None = None,
    row_identity: str | None = None,
    column: str | None = None,
    captured_at: str | None = None,
    version: str | None = None,
    title: str | None = None,
    display_text: str | None = None,
) -> SourceLocator:
    """Normalize one read-only MySQL row; no SQL or credentials are retained."""
    alias = _identifier(
        connection_alias
        if connection_alias is not None
        else _get(row, "connection_alias"),
        "connection_alias",
        alias=True,
    )
    db = _identifier(
        database if database is not None else _get(row, "database"), "database"
    )
    table_name = _identifier(
        table if table is not None else _get(row, "table"), "table"
    )
    sql = query if query is not None else _get(row, "query")
    if not isinstance(sql, str):
        raise LocatorError("query is required for a MySQL locator")
    _canonical, fingerprint = _canonical_sql(sql, db)
    identity = row_identity if row_identity is not None else _get(row, "row_identity")
    if identity is None:
        raw_row = _get(row, "row", row)
        identity = _get(raw_row, "id") if isinstance(raw_row, Mapping) else None
    if identity is None:
        raise LocatorError("row_identity is required for a MySQL locator")
    identity = _text(str(identity), "row_identity", max_length=128)
    col = _identifier(column if column is not None else _get(row, "column"), "column")
    captured, release = _metadata(row, captured_at, version)
    heading = redact(title) if title is not None else f"{db}.{table_name}"
    text = display_text if display_text is not None else str(_get(row, "row", row))
    return SourceLocator(
        SourceKind.MYSQL,
        _text(heading, "title", max_length=200),
        captured,
        release,
        _bounded_display(text),
        MySQLLocator(alias, db, table_name, fingerprint, identity, col),
    )


def normalize_knowledge_chunk(
    chunk: Any,
    *,
    collection_id: str | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    captured_at: str | None = None,
    version: str | None = None,
    title: str | None = None,
    display_text: str | None = None,
) -> SourceLocator:
    """Normalize vendor-neutral collection/document/chunk identity metadata."""
    collection = _identifier(
        collection_id if collection_id is not None else _get(chunk, "collection_id"),
        "collection_id",
    )
    document = _identifier(
        document_id if document_id is not None else _get(chunk, "document_id"),
        "document_id",
    )
    chunk_value = _identifier(
        chunk_id if chunk_id is not None else _get(chunk, "chunk_id"), "chunk_id"
    )
    captured, release = _metadata(chunk, captured_at, version)
    heading = redact(title) if title is not None else f"{collection}/{document}"
    text = (
        display_text
        if display_text is not None
        else _get(chunk, "content", _get(chunk, "answer", "Knowledge source"))
    )
    return SourceLocator(
        SourceKind.KNOWLEDGE,
        _text(heading, "title", max_length=200),
        captured,
        release,
        _bounded_display(text),
        KnowledgeChunkLocator(collection, document, chunk_value),
    )


def normalize_uploaded_span(
    span: Any,
    *,
    expected_thread_id: str | None = None,
    captured_at: str | None = None,
    version: str | None = None,
    title: str | None = None,
    display_text: str | None = None,
) -> SourceLocator:
    """Normalize a thread-scoped upload position.

    Absolute paths never enter the locator.
    """
    thread_id = _text(_get(span, "thread_id"), "thread_id", max_length=64).lower()
    if not _UUID_RE.fullmatch(thread_id):
        raise LocatorError("thread_id must be a UUID")
    if expected_thread_id is not None:
        expected = _text(
            expected_thread_id, "expected_thread_id", max_length=64
        ).lower()
        if not _UUID_RE.fullmatch(expected):
            raise LocatorError("expected_thread_id must be a UUID")
        if thread_id != expected:
            raise LocatorError("uploaded locator belongs to a different thread")
    artifact = _text(
        _get(span, "artifact_name", _get(span, "name")), "artifact_name", max_length=255
    )
    if (
        artifact != artifact.split("/")[-1]
        or artifact != artifact.split("\\")[-1]
        or artifact in {".", ".."}
    ):
        raise LocatorError(f"artifact_name must be a basename: {artifact!r}")
    position_raw = _get(span, "position", span)
    position = FilePosition(
        page=_get(position_raw, "page"),
        line_start=_get(position_raw, "line_start"),
        line_end=_get(position_raw, "line_end"),
        char_start=_get(position_raw, "char_start"),
        char_end=_get(position_raw, "char_end"),
    )
    captured, release = _metadata(span, captured_at, version)
    heading = redact(title) if title is not None else artifact
    text = (
        display_text
        if display_text is not None
        else _get(span, "content", "Uploaded source")
    )
    link = f"/api/threads/{thread_id}/uploads/{quote(artifact, safe='')}"
    return SourceLocator(
        SourceKind.UPLOADED_FILE,
        _text(heading, "title", max_length=200),
        captured,
        release,
        _bounded_display(text),
        UploadedFileLocator(thread_id, artifact, position),
        thread_id=thread_id,
        safe_display_link=link,
    )
