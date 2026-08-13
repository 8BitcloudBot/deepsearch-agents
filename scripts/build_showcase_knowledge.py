#!/usr/bin/env python3
"""Build the small Showcase knowledge manifest from explicit local sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CHUNKING_VERSION = "semantic-markdown-v1"
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_MARKDOWN_IMAGE_RE = re.compile(r"^\s*!\[[^]]*]\([^)]*\)\s*$")
_HTML_ONLY_RE = re.compile(r"^\s*<[^>]+>.*</[^>]+>\s*$")


def _safe_source_path(source_root: Path, configured: str) -> Path:
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError("source path is invalid")
    relative = Path(configured)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("source path is unsafe")
    root = source_root.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError("source file is unavailable")
    return resolved


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_entry(raw: object, default_url: str) -> tuple[str, str, str | None]:
    if isinstance(raw, str):
        return raw, default_url, None
    if not isinstance(raw, dict):
        raise ValueError("source entry is invalid")
    if set(raw) != {"path", "source_url", "content_sha256"}:
        raise ValueError("source entry fields are invalid")
    path = raw["path"]
    source_url = raw["source_url"]
    content_sha256 = raw["content_sha256"]
    if not all(isinstance(value, str) for value in (path, source_url, content_sha256)):
        raise ValueError("source entry fields are invalid")
    return path, source_url, content_sha256


def _clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    in_front_matter = text.startswith("---\n")
    in_html_block = False
    for index, raw_line in enumerate(text.splitlines()):
        line = raw_line.rstrip()
        if in_front_matter:
            if index > 0 and line == "---":
                in_front_matter = False
            continue
        if line.lstrip().startswith("<h1") or line.lstrip().startswith("<p align="):
            in_html_block = True
        if in_html_block:
            if line.strip().endswith("</h1>") or line.strip().endswith("</p>"):
                in_html_block = False
            continue
        if _MARKDOWN_IMAGE_RE.match(line) or _HTML_ONLY_RE.match(line):
            continue
        lines.append(line)
    return lines


def _sections(text: str, *, fallback_title: str) -> list[tuple[list[str], list[str]]]:
    headings: list[str] = [fallback_title]
    blocks: list[str] = []
    sections: list[tuple[list[str], list[str]]] = []
    paragraph: list[str] = []
    in_fence = False

    def flush_paragraph() -> None:
        if paragraph:
            block = "\n".join(paragraph).strip()
            if block:
                blocks.append(block)
            paragraph.clear()

    def flush_section() -> None:
        flush_paragraph()
        if blocks:
            sections.append((headings.copy(), blocks.copy()))
            blocks.clear()

    for line in _clean_lines(text):
        fence = _FENCE_RE.match(line)
        if fence:
            paragraph.append(line)
            in_fence = not in_fence
            continue
        heading = None if in_fence else _HEADING_RE.match(line)
        if heading:
            flush_section()
            level = len(heading.group(1))
            title = re.sub(r"\s+#+$", "", heading.group(2)).strip()
            if level == 1:
                headings = [title]
            else:
                headings = headings[: level - 1]
                while len(headings) < level - 1:
                    headings.append(headings[-1])
                headings.append(title)
            continue
        if not line.strip() and not in_fence:
            flush_paragraph()
        else:
            paragraph.append(line)
    flush_section()
    return sections


def _group_blocks(blocks: list[str], *, max_chars: int = 1800) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    current_size = 0
    for block in blocks:
        addition = len(block) + (2 if current else 0)
        if current and current_size + addition > max_chars:
            groups.append("\n\n".join(current))
            current = []
            current_size = 0
        current.append(block)
        current_size += len(block) + (2 if len(current) > 1 else 0)
    if current:
        groups.append("\n\n".join(current))
    return groups


def _document_chunks(
    document: dict[str, Any], *, source_root: Path
) -> list[dict[str, str | None]]:
    local_sources = document.get("local_sources")
    if not isinstance(local_sources, list) or not local_sources:
        raise ValueError("document local sources are invalid")
    default_url = document.get("source_url")
    if not isinstance(default_url, str):
        raise ValueError("document source URL is invalid")
    expected_document_hash = document.get("content_sha256")
    chunks: list[dict[str, str | None]] = []
    raw_payloads: list[bytes] = []
    sequence = 0
    for raw_source in local_sources:
        configured, source_url, expected_hash = _source_entry(raw_source, default_url)
        source_path = _safe_source_path(source_root, configured)
        payload = source_path.read_bytes()
        raw_payloads.append(payload)
        if expected_hash is not None and _sha256(payload) != expected_hash:
            raise ValueError("source hash does not match catalog")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("source is not valid UTF-8") from exc
        for headings, blocks in _sections(text, fallback_title=str(document["title"])):
            for content in _group_blocks(blocks):
                sequence += 1
                section_path = " > ".join(dict.fromkeys(headings))
                chunks.append(
                    {
                        "chunk_id": f"{document['document_id']}-{sequence:04d}",
                        "content": content,
                        "section_path": section_path,
                        "source_uri": source_url,
                    }
                )
    if len(raw_payloads) == 1 and isinstance(expected_document_hash, str):
        if _sha256(raw_payloads[0]) != expected_document_hash:
            raise ValueError("document source hash does not match catalog")
    if not chunks:
        raise ValueError("document has no semantic chunks")
    return chunks


def build_manifest(catalog: dict[str, Any], *, source_root: Path) -> dict[str, Any]:
    collection = catalog.get("collection_id")
    documents = catalog.get("documents")
    if (
        not isinstance(collection, str)
        or not isinstance(documents, list)
        or not documents
    ):
        raise ValueError("source catalog is invalid")
    manifest_documents: list[dict[str, Any]] = []
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("source catalog document is invalid")
        required = ("document_id", "title", "source_version", "source_url")
        if not all(isinstance(document.get(field), str) for field in required):
            raise ValueError("source catalog document is invalid")
        manifest_documents.append(
            {
                "document_id": document["document_id"],
                "title": document["title"],
                "version": document["source_version"],
                "chunks": _document_chunks(document, source_root=source_root),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "collection_id": collection,
        "chunking_version": CHUNKING_VERSION,
        "documents": manifest_documents,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        manifest = build_manifest(catalog, source_root=args.source_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        print("[build-showcase-knowledge] error: corpus input is invalid")
        return 2
    chunk_count = sum(len(document["chunks"]) for document in manifest["documents"])
    document_count = len(manifest["documents"])
    print(
        f"collection={manifest['collection_id']} documents={document_count} "
        f"chunks={chunk_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
