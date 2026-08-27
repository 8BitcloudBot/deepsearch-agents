"""Schema 5.0 value objects for one conversation turn."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "5.0.0"
SourceKind = Literal["knowledge", "session_file", "web"]
LocatorKind = Literal["url", "chunk", "file"]


def _text(value: object, field: str, maximum: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True)
class TurnResearchPlan:
    objective: str
    subquestions: tuple[str, ...]
    knowledge_queries: tuple[str, ...]
    web_queries: tuple[str, ...]
    research_intensity: Literal["standard", "deep"] | None = None
    search_hints: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "objective", _text(self.objective, "objective"))
        if self.research_intensity not in (None, "standard", "deep"):
            raise ValueError("research_intensity is invalid")
        if self.search_hints:
            hints = tuple(
                (str(key), str(value)) for key, value in dict(self.search_hints).items()
            )
            object.__setattr__(self, "search_hints", hints)
        for field, maximum in (
            ("subquestions", 3),
            ("knowledge_queries", 2),
            ("web_queries", 3),
        ):
            values = getattr(self, field)
            if not isinstance(values, tuple) or len(values) > maximum:
                label = field.replace("_", " ")
                raise ValueError(f"{label} exceed the allowed limit")
            cleaned = tuple(_text(value, field, 4096) for value in values)
            if len(cleaned) != len(set(value.casefold() for value in cleaned)):
                raise ValueError(f"{field} contain duplicates")
            object.__setattr__(self, field, cleaned)

    def hint(self, key: str) -> str | None:
        for name, value in self.search_hints:
            if name == key:
                return value
        return None

    def as_dict(self) -> dict[str, object]:
        return {
            "objective": self.objective,
            "subquestions": list(self.subquestions),
            "knowledge_queries": list(self.knowledge_queries),
            "web_queries": list(self.web_queries),
            "research_intensity": self.research_intensity,
            "search_hints": dict(self.search_hints) if self.search_hints else {},
        }


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_kind: SourceKind
    title: str
    locator_kind: LocatorKind
    locator_value: str
    quote: str
    hostname: str | None = None
    published_at: str | None = None
    score: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _text(self.evidence_id, "evidence_id", 128)
        )
        if self.source_kind not in {"knowledge", "session_file", "web"}:
            raise ValueError("source_kind is invalid")
        if self.locator_kind not in {"url", "chunk", "file"}:
            raise ValueError("locator_kind is invalid")
        object.__setattr__(self, "title", _text(self.title, "title", 512))
        object.__setattr__(
            self, "locator_value", _text(self.locator_value, "locator_value", 2048)
        )
        object.__setattr__(self, "quote", _text(self.quote, "quote", 2000))
        if self.score is not None:
            if (
                isinstance(self.score, bool)
                or not isinstance(self.score, int | float)
                or not math.isfinite(self.score)
            ):
                raise ValueError("score must be a finite number when present")
            object.__setattr__(self, "score", float(self.score))

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_kind": self.source_kind,
            "title": self.title,
            "locator_kind": self.locator_kind,
            "locator_value": self.locator_value,
            "quote": self.quote,
            "hostname": self.hostname,
            "published_at": self.published_at,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, payload: object) -> EvidenceItem:
        if not isinstance(payload, dict):
            raise ValueError("evidence item is invalid")
        return cls(
            evidence_id=payload.get("evidence_id"),
            source_kind=payload.get("source_kind"),
            title=payload.get("title"),
            locator_kind=payload.get("locator_kind"),
            locator_value=payload.get("locator_value"),
            quote=payload.get("quote"),
            hostname=payload.get("hostname"),
            published_at=payload.get("published_at"),
            score=payload.get("score"),
        )


@dataclass(frozen=True)
class Claim:
    claim_id: str
    statement: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _text(self.claim_id, "claim_id", 128))
        object.__setattr__(self, "statement", _text(self.statement, "statement", 4000))
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids:
            raise ValueError("claim must reference evidence")
        ids = tuple(_text(value, "evidence_id", 128) for value in self.evidence_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("claim contains duplicate evidence")
        object.__setattr__(self, "evidence_ids", ids)

    def as_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "statement": self.statement,
            "evidence_ids": list(self.evidence_ids),
        }

    @classmethod
    def from_dict(cls, payload: object) -> Claim:
        if not isinstance(payload, dict) or not isinstance(
            payload.get("evidence_ids"), list
        ):
            raise ValueError("claim is invalid")
        return cls(
            claim_id=payload.get("claim_id"),
            statement=payload.get("statement"),
            evidence_ids=tuple(payload["evidence_ids"]),
        )


@dataclass(frozen=True)
class TurnResult:
    schema_version: Literal["5.0.0"]
    answer: str
    claims: tuple[Claim, ...]
    evidence: tuple[EvidenceItem, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("schema_version must be 5.0.0")
        object.__setattr__(self, "answer", _text(self.answer, "answer", 20000))
        if not isinstance(self.claims, tuple) or not isinstance(self.evidence, tuple):
            raise ValueError("claims and evidence must be tuples")
        known = {item.evidence_id for item in self.evidence}
        if len(known) != len(self.evidence):
            raise ValueError("duplicate evidence IDs")
        for claim in self.claims:
            unknown = set(claim.evidence_ids) - known
            if unknown:
                raise ValueError("claim references unknown evidence")
        object.__setattr__(
            self,
            "limitations",
            tuple(_text(value, "limitation", 2000) for value in self.limitations),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "answer": self.answer,
            "claims": [claim.as_dict() for claim in self.claims],
            "evidence": [item.as_dict() for item in self.evidence],
            "limitations": list(self.limitations),
        }

    @classmethod
    def from_dict(cls, payload: object) -> TurnResult:
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("claims"), list)
            or not isinstance(payload.get("evidence"), list)
            or not isinstance(payload.get("limitations"), list)
        ):
            raise ValueError("turn result is invalid")
        return cls(
            schema_version=payload.get("schema_version"),
            answer=payload.get("answer"),
            claims=tuple(Claim.from_dict(item) for item in payload["claims"]),
            evidence=tuple(
                EvidenceItem.from_dict(item) for item in payload["evidence"]
            ),
            limitations=tuple(payload["limitations"]),
        )
