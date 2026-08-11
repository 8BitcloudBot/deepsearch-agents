"""Canonical live citation delivery for the P4.5 showcase runtime."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import quote

from app.agent.runtime import RuntimeRequest
from app.api.events import InMemoryEventBus
from app.citations.rules import redact
from app.showcase.contracts import (
    Limitation,
    SourceKind,
    validate_live_source_result,
)
from app.showcase.locators import SourceLocator
from app.showcase.research import ShowcaseRunResult
from app.tools.files import SessionWorkspace, _atomic_write_bytes
from app.tools.reports import generate_markdown_report, generate_pdf_report

LIVE_CITATION_SCHEMA_VERSION = "2.0.0"
LIVE_CITATION_FILENAME = "live-citations.json"
SHOWCASE_MARKDOWN_FILENAME = "showcase-report.md"
SHOWCASE_PDF_FILENAME = "showcase-report.pdf"

_ARTIFACTS = (
    (LIVE_CITATION_FILENAME, "application/json"),
    (SHOWCASE_MARKDOWN_FILENAME, "text/markdown"),
    (SHOWCASE_PDF_FILENAME, "application/pdf"),
)
_STAGED_FILENAMES = (
    ".showcase-stage.json",
    ".showcase-stage.md",
    ".showcase-stage.pdf",
)
_ID_RE = re.compile(r"^(?:claim|ev-live)-[A-Za-z0-9-]+$")


@dataclass(frozen=True)
class DeliveryClaim:
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True)
class LiveCitationDocument:
    thread_id: str
    answer: str
    claims: tuple[DeliveryClaim, ...]
    sources: tuple[dict[str, object], ...]
    evidence: tuple[dict[str, object], ...]
    limitations: tuple[dict[str, object], ...]
    artifacts: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": LIVE_CITATION_SCHEMA_VERSION,
            "thread_id": self.thread_id,
            "answer": self.answer,
            "claims": [claim.as_dict() for claim in self.claims],
            "sources": [dict(source) for source in self.sources],
            "evidence": [dict(item) for item in self.evidence],
            "limitations": [dict(item) for item in self.limitations],
            "artifacts": list(self.artifacts),
        }

    def as_json(self) -> str:
        return (
            json.dumps(
                self.as_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
            + "\n"
        )


@dataclass(frozen=True)
class ShowcaseDeliveryResult:
    artifacts: tuple[str, ...]
    limitations: tuple[Limitation, ...] = ()


def _paragraphs(answer: str) -> tuple[str, ...]:
    paragraphs: list[str] = []
    for raw in re.split(r"(?:\r?\n){2,}", answer):
        paragraph = redact(raw.strip())
        if paragraph:
            paragraphs.append(paragraph)
    return tuple(paragraphs)


def _source_record(thread_id: str, source: SourceLocator) -> dict[str, object]:
    expected_thread = (
        thread_id if source.source_kind is SourceKind.UPLOADED_FILE else None
    )
    record = source.as_live_source_result(expected_thread_id=expected_thread)
    if source.safe_display_link is not None:
        record["safe_display_link"] = source.safe_display_link
    return record


def build_live_citation_document(
    thread_id: str, result: ShowcaseRunResult
) -> LiveCitationDocument:
    answer = redact(result.answer) if isinstance(result.answer, str) else ""
    evidence_ids = tuple(item.evidence_id for item in result.evidence)
    claims = tuple(
        DeliveryClaim(f"claim-{index}", paragraph, evidence_ids)
        for index, paragraph in enumerate(_paragraphs(answer), start=1)
    )
    limitations = [
        {
            "code": limitation.code,
            "source_kind": (
                limitation.source_kind.value if limitation.source_kind else None
            ),
            "message": redact(limitation.message),
        }
        for limitation in result.limitations
    ]
    if not result.evidence and not limitations:
        limitations.append(
            {
                "code": "no-evidence",
                "source_kind": None,
                "message": "no live evidence was collected",
            }
        )
    return LiveCitationDocument(
        thread_id=thread_id,
        answer=answer,
        claims=claims,
        sources=tuple(_source_record(thread_id, source) for source in result.sources),
        evidence=tuple(item.as_dict() for item in result.evidence),
        limitations=tuple(limitations),
        artifacts=tuple(name for name, _media_type in _ARTIFACTS),
    )


def _safe_link(source: Mapping[str, object]) -> str | None:
    link = source.get("safe_display_link")
    if not isinstance(link, str):
        return None
    if link.startswith(("https://", "http://", "/api/threads/")):
        return link
    return None


def render_showcase_markdown(document: LiveCitationDocument) -> str:
    lines = ["# Showcase Research Report", "", "## Answer", ""]
    if document.claims:
        for claim in document.claims:
            lines.extend((f"[{claim.claim_id}] {claim.statement}", ""))
    else:
        lines.extend(("No answer claims were produced.", ""))

    lines.extend(("## Claims and Evidence", ""))
    if document.claims:
        for claim in document.claims:
            evidence = ", ".join(claim.evidence_ids) or "none"
            lines.extend(
                (f"- {claim.claim_id}: {claim.statement}", f"  Evidence: {evidence}")
            )
    else:
        lines.append("- No claims.")
    lines.append("")

    lines.extend(("## Evidence", ""))
    if document.evidence:
        for item in document.evidence:
            lines.append(
                f"- {item['evidence_id']}: {redact(str(item['quote']))} "
                f"(source {item['source_id']}; {item['locator']['kind']}="
                f"{item['locator']['value']})"
            )
    else:
        lines.append("- No evidence was collected.")
    lines.append("")

    lines.extend(("## Sources", ""))
    if document.sources:
        for source in document.sources:
            lines.append(
                f"- {source['title']} ({source['source_kind']}); "
                f"captured {source['captured_at']}; version {source['version']}"
            )
            locator = source["locator"]
            lines.append(f"  Locator: {locator['kind']}={locator['value']}")
            if link := _safe_link(source):
                lines.append(f"  Link: {link}")
    else:
        lines.append("- No valid sources were collected.")
    lines.append("")

    if document.limitations:
        lines.extend(("## Limitations", ""))
        for limitation in document.limitations:
            kind = limitation.get("source_kind") or "general"
            lines.append(
                f"- {limitation['code']} ({kind}): {redact(str(limitation['message']))}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _require_string(value: object, field: str, *, non_empty: bool = True) -> str:
    if not isinstance(value, str) or (non_empty and not value.strip()):
        raise ValueError(f"invalid live citation {field}")
    if redact(value) != value:
        raise ValueError(f"invalid live citation {field}")
    return value


def validate_live_citation_document(
    value: Mapping[str, object], *, expected_thread_id: str
) -> dict[str, object]:
    """Validate persisted live citation JSON before returning it from the API."""
    required = {
        "schema_version",
        "thread_id",
        "answer",
        "claims",
        "sources",
        "evidence",
        "limitations",
        "artifacts",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("invalid live citation document")
    if value["schema_version"] != LIVE_CITATION_SCHEMA_VERSION:
        raise ValueError("invalid live citation schema")
    if value["thread_id"] != expected_thread_id:
        raise ValueError("live citation thread mismatch")
    _require_string(value["answer"], "answer", non_empty=False)
    artifacts = value["artifacts"]
    if artifacts != [name for name, _media_type in _ARTIFACTS]:
        raise ValueError("invalid live citation artifacts")

    claims = value["claims"]
    if not isinstance(claims, list):
        raise ValueError("invalid live citation claims")
    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, Mapping) or set(claim) != {
            "claim_id",
            "statement",
            "evidence_ids",
        }:
            raise ValueError("invalid live citation claim")
        if claim["claim_id"] != f"claim-{index}":
            raise ValueError("invalid live citation claim id")
        _require_string(claim["statement"], "claim statement")
        if not isinstance(claim["evidence_ids"], list) or not all(
            isinstance(item, str) and _ID_RE.fullmatch(item)
            for item in claim["evidence_ids"]
        ):
            raise ValueError("invalid live citation evidence ids")

    sources = value["sources"]
    if not isinstance(sources, list):
        raise ValueError("invalid live citation sources")
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("invalid live citation source")
        safe_link = source.get("safe_display_link")
        source_for_contract = dict(source)
        source_for_contract.pop("safe_display_link", None)
        validate_live_source_result(source_for_contract)
        source_kind = source["source_kind"]
        locator = source["locator"]
        if source_kind == SourceKind.WEB.value:
            if safe_link != locator["value"] or not _safe_link(source):
                raise ValueError("invalid live citation display link")
        elif source_kind == SourceKind.UPLOADED_FILE.value:
            artifact_name = locator["value"].split(":", 1)[0]
            expected_link = (
                f"/api/threads/{expected_thread_id}/uploads/"
                f"{quote(artifact_name, safe='')}"
            )
            if safe_link != expected_link:
                raise ValueError("invalid live citation display link")
        elif safe_link is not None:
            raise ValueError("invalid live citation display link")

    evidence = value["evidence"]
    if not isinstance(evidence, list):
        raise ValueError("invalid live citation evidence")
    evidence_ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, Mapping) or set(item) != {
            "evidence_id",
            "source_id",
            "source_kind",
            "locator",
            "quote",
            "content_sha256",
            "thread_id",
        }:
            raise ValueError("invalid live citation evidence")
        evidence_id = item["evidence_id"]
        if not isinstance(evidence_id, str) or not _ID_RE.fullmatch(evidence_id):
            raise ValueError("invalid live citation evidence id")
        evidence_ids.add(evidence_id)
        _require_string(item["quote"], "evidence quote")
        if not isinstance(item["locator"], Mapping):
            raise ValueError("invalid live citation evidence locator")
    for claim in claims:
        if not set(claim["evidence_ids"]).issubset(evidence_ids):
            raise ValueError("claim references unknown evidence")

    limitations = value["limitations"]
    if not isinstance(limitations, list):
        raise ValueError("invalid live citation limitations")
    for limitation in limitations:
        if not isinstance(limitation, Mapping) or set(limitation) != {
            "code",
            "source_kind",
            "message",
        }:
            raise ValueError("invalid live citation limitation")
        _require_string(limitation["code"], "limitation code")
        _require_string(limitation["message"], "limitation message")
    return dict(value)


def _write_json(workspace: SessionWorkspace, filename: str, content: str) -> None:
    target = workspace.resolve_output(filename)
    _atomic_write_bytes(target, content.encode("utf-8"))


class ShowcaseCitationDelivery:
    def __init__(self, events: InMemoryEventBus):
        self._events = events

    def deliver(
        self, request: RuntimeRequest, result: ShowcaseRunResult
    ) -> ShowcaseDeliveryResult:
        thread_id = request.context.thread_id
        document = build_live_citation_document(thread_id, result)
        markdown = render_showcase_markdown(document)
        self._events.emit(
            thread_id,
            "citation_started",
            "showcase delivery",
            {
                "claim_count": len(document.claims),
                "evidence_count": len(document.evidence),
            },
        )
        workspace = request.context.workspace
        staged = _STAGED_FILENAMES
        try:
            _write_json(workspace, staged[0], document.as_json())
            generate_markdown_report(markdown, filename=staged[1])
            generate_pdf_report(markdown, filename=staged[2])
            for source, target in zip(
                staged, (name for name, _media_type in _ARTIFACTS)
            ):
                os.replace(
                    workspace.resolve_output(source), workspace.resolve_output(target)
                )
        except Exception:
            for filename in staged:
                try:
                    path = workspace.resolve_output(filename)
                    if path.exists() or path.is_symlink():
                        path.unlink()
                except Exception:
                    pass
            limitation = Limitation("delivery-failed", None, "showcase delivery failed")
            self._events.emit(
                thread_id,
                "citation_completed",
                "showcase delivery",
                {"status": "degraded"},
            )
            return ShowcaseDeliveryResult((), (limitation,))

        for name, media_type in _ARTIFACTS:
            self._events.emit(
                thread_id,
                "artifact_created",
                name,
                {"name": name, "path": name, "media_type": media_type},
            )
        self._events.emit(
            thread_id,
            "citation_completed",
            "showcase delivery",
            {"status": "completed"},
        )
        return ShowcaseDeliveryResult(document.artifacts)


__all__ = [
    "LIVE_CITATION_FILENAME",
    "LIVE_CITATION_SCHEMA_VERSION",
    "SHOWCASE_MARKDOWN_FILENAME",
    "SHOWCASE_PDF_FILENAME",
    "DeliveryClaim",
    "LiveCitationDocument",
    "ShowcaseCitationDelivery",
    "ShowcaseDeliveryResult",
    "build_live_citation_document",
    "render_showcase_markdown",
    "validate_live_citation_document",
]
