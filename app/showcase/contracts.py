"""Frozen P4.5-1 showcase profile and live-source contracts.

This module is the P4.5-1 contract surface. It defines:

* the dedicated showcase opt-in (``SHOWCASE_ENABLED``, enabled only by the
  exact value ``"1"``) and the explicit per-source capability declaration
  (``SHOWCASE_SOURCES``);
* :func:`resolve_capabilities`, a pure fail-closed capability check that
  never reads credentials, never touches the network and never constructs
  providers — missing, invalid or disabled capabilities yield structured
  :class:`Limitation` records instead of enabling anything;
* the frozen normalized live-source result contract
  (:func:`validate_live_source_result`) that downstream adapters consume
  in P4.5-2+: stable source identity, title, captured/version metadata,
  bounded display text and a validated typed-locator boundary.

Offline and showcase/live execution and evidence partitions are distinct
in the contract: a live-source result must declare ``execution_mode`` and
``evidence_partition`` as ``"live"``, so live evidence can never be
relabeled as offline and offline fixtures can never masquerade as live
source results.

P4.5-1 deliberately implements no concrete source adapters and no locator
resolution — the locator boundary only pins each source kind's allowed
locator kinds and the bounded ``{kind, value}`` shape.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "1.0.0"

SHOWCASE_ENABLED_ENV = "SHOWCASE_ENABLED"
SHOWCASE_SOURCES_ENV = "SHOWCASE_SOURCES"


class SourceKind(StrEnum):
    """The four future live-source kinds (frozen for P4.5-2)."""

    WEB = "web"
    MYSQL = "mysql"
    RAGFLOW = "ragflow"
    UPLOADED_FILE = "uploaded-file"


LIVE_SOURCE_KINDS: tuple[SourceKind, ...] = (
    SourceKind.WEB,
    SourceKind.MYSQL,
    SourceKind.RAGFLOW,
    SourceKind.UPLOADED_FILE,
)


class ExecutionMode(StrEnum):
    """Execution partition: offline (deterministic) vs live (showcase)."""

    OFFLINE = "offline"
    LIVE = "live"


class EvidencePartition(StrEnum):
    """Evidence partition: offline fixtures vs live-source evidence."""

    OFFLINE = "offline"
    LIVE = "live"


class RecordType(StrEnum):
    LIVE_SOURCE_RESULT = "live_source_result"


@dataclass(frozen=True)
class Limitation:
    """One structured, JSON-safe fail-closed capability limitation."""

    code: str
    source_kind: SourceKind | None
    message: str

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "source_kind": self.source_kind.value if self.source_kind else None,
            "message": self.message,
        }


@dataclass(frozen=True)
class CapabilityState:
    """Fail-closed capability state for one source kind."""

    source_kind: SourceKind
    enabled: bool
    limitations: tuple[Limitation, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind.value,
            "enabled": self.enabled,
            "limitations": [limitation.as_dict() for limitation in self.limitations],
        }


@dataclass(frozen=True)
class ShowcaseCapabilities:
    """Explicit showcase capability surface.

    ``enabled`` is true only when ``SHOWCASE_ENABLED`` is exactly ``"1"``.
    A source is capable only when it is both enabled and explicitly
    declared in ``SHOWCASE_SOURCES``; every other combination fails closed
    with a structured limitation.
    """

    enabled: bool
    states: tuple[CapabilityState, ...]
    invalid_declarations: tuple[str, ...] = ()

    def check(self, kind: SourceKind | str) -> CapabilityState:
        """Return the fail-closed capability state for one source kind."""
        if isinstance(kind, str):
            kind = SourceKind(kind)
        for state in self.states:
            if state.source_kind is kind:
                return state
        raise ValueError(f"unknown source kind {kind.value!r}")

    def limitations(self) -> tuple[Limitation, ...]:
        """Every structured limitation, including invalid declarations."""
        result = [
            limitation for state in self.states for limitation in state.limitations
        ]
        for token in self.invalid_declarations:
            result.append(
                Limitation(
                    code="invalid-source",
                    source_kind=None,
                    message=(
                        f"unknown source kind {token!r} in {SHOWCASE_SOURCES_ENV}; "
                        "allowed: "
                        f"{', '.join(kind.value for kind in LIVE_SOURCE_KINDS)}"
                    ),
                )
            )
        return tuple(result)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "enabled": self.enabled,
            "sources": [state.as_dict() for state in self.states],
            "invalid_declarations": list(self.invalid_declarations),
        }


def resolve_capabilities(environ: Mapping[str, str]) -> ShowcaseCapabilities:
    """Resolve the explicit showcase capability surface from an env mapping.

    Pure and fail-closed: reads only the opt-in and source-declaration
    keys, never credentials, and never constructs providers. ``None`` is
    not accepted — callers must pass the exact mapping to inspect.
    """
    opt_in = environ.get(SHOWCASE_ENABLED_ENV)
    enabled = opt_in == "1"

    declared: set[SourceKind] = set()
    invalid: list[str] = []
    for token in environ.get(SHOWCASE_SOURCES_ENV, "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            declared.add(SourceKind(token))
        except ValueError:
            invalid.append(token)

    states: list[CapabilityState] = []
    for kind in LIVE_SOURCE_KINDS:
        if not enabled:
            limitation = Limitation(
                code="opt-in-disabled",
                source_kind=kind,
                message=(
                    f"{SHOWCASE_ENABLED_ENV} must be exactly '1' to enable "
                    f"showcase live sources (got {opt_in!r})"
                ),
            )
            states.append(CapabilityState(kind, False, (limitation,)))
        elif kind in declared:
            states.append(CapabilityState(kind, True, ()))
        else:
            limitation = Limitation(
                code="not-enabled",
                source_kind=kind,
                message=(
                    f"source kind {kind.value!r} is not explicitly enabled in "
                    f"{SHOWCASE_SOURCES_ENV}"
                ),
            )
            states.append(CapabilityState(kind, False, (limitation,)))

    return ShowcaseCapabilities(
        enabled=enabled,
        states=tuple(states),
        invalid_declarations=tuple(invalid),
    )


# ── frozen normalized live-source result contract ──────────────────────────


LIVE_SOURCE_RESULT_FIELDS = frozenset(
    {
        "type",
        "source_id",
        "source_kind",
        "title",
        "captured_at",
        "version",
        "display_text",
        "locator",
        "execution_mode",
        "evidence_partition",
    }
)
LOCATOR_FIELDS = frozenset({"kind", "value"})

MAX_TITLE_LENGTH = 200
MAX_DISPLAY_TEXT_LENGTH = 2048
MAX_LOCATOR_VALUE_LENGTH = 512

_SOURCE_ID_RE = re.compile(r"^src-[a-z0-9][a-z0-9-]{0,63}$")
_CAPTURED_AT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

# Typed-locator boundary for P4.5-2: each source kind pins the allowed
# locator kinds; the payload shape stays the bounded {kind, value} pair
# until P4.5-2 adds per-kind typed locators.
LOCATOR_KINDS_BY_SOURCE_KIND: dict[SourceKind, frozenset[str]] = {
    SourceKind.WEB: frozenset({"url"}),
    SourceKind.MYSQL: frozenset({"row"}),
    SourceKind.RAGFLOW: frozenset({"chunk"}),
    SourceKind.UPLOADED_FILE: frozenset({"span"}),
}


class LiveSourceResultError(ValueError):
    """A live-source result violated the frozen P4.5-1 contract."""

    def __init__(self, message: str, *, path: str = "$") -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


def _check_fields(raw: Any, required: frozenset[str], what: str, path: str) -> None:
    if not isinstance(raw, Mapping):
        raise LiveSourceResultError(f"{what} must be a JSON object", path=path)
    unknown = sorted(set(raw) - set(required))
    if unknown:
        raise LiveSourceResultError(
            f"{what} has unknown field(s): {', '.join(unknown)}", path=path
        )
    missing = sorted(set(required) - set(raw))
    if missing:
        raise LiveSourceResultError(
            f"{what} is missing required field(s): {', '.join(missing)}", path=path
        )


def _enum(raw: Any, enum_cls: type[StrEnum], field: str, path: str) -> StrEnum:
    if not isinstance(raw, str):
        raise LiveSourceResultError(f"{field} must be a string", path=f"{path}.{field}")
    try:
        return enum_cls(raw)
    except ValueError:
        allowed = ", ".join(sorted(member.value for member in enum_cls))
        raise LiveSourceResultError(
            f"{field} must be one of: {allowed}", path=f"{path}.{field}"
        )


def _bounded_text(
    raw: Any,
    field: str,
    path: str,
    max_length: int,
) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise LiveSourceResultError(
            f"{field} must be a non-empty string", path=f"{path}.{field}"
        )
    if len(raw) > max_length:
        raise LiveSourceResultError(
            f"{field} must be at most {max_length} characters",
            path=f"{path}.{field}",
        )
    if any(ord(ch) < 0x20 for ch in raw):
        raise LiveSourceResultError(
            f"{field} must not contain control characters", path=f"{path}.{field}"
        )
    return raw


def _source_id(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not _SOURCE_ID_RE.fullmatch(raw):
        raise LiveSourceResultError(
            "source_id is malformed; expected pattern 'src-<slug>'",
            path=f"{path}.source_id",
        )
    return raw


def _captured_at(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not _CAPTURED_AT_RE.fullmatch(raw):
        raise LiveSourceResultError(
            "captured_at must be an ISO-8601 UTC timestamp with timezone "
            "(e.g. 2026-08-08T12:00:00Z)",
            path=f"{path}.captured_at",
        )
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise LiveSourceResultError(
            "captured_at is not a valid ISO-8601 timestamp",
            path=f"{path}.captured_at",
        )
    return raw


def _version(raw: Any, path: str) -> str:
    if not isinstance(raw, str) or not _VERSION_RE.fullmatch(raw):
        raise LiveSourceResultError(
            "version must be a valid semantic version (e.g. 1.2.3 or 1.2.3-rc.1)",
            path=f"{path}.version",
        )
    return raw


def _locator(raw: Any, source_kind: SourceKind, path: str) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise LiveSourceResultError(
            "locator must be a JSON object", path=f"{path}.locator"
        )
    _check_fields(raw, LOCATOR_FIELDS, "locator", f"{path}.locator")
    kind, value = raw["kind"], raw["value"]
    if not isinstance(kind, str) or not kind:
        raise LiveSourceResultError(
            "locator.kind must be a non-empty string", path=f"{path}.locator.kind"
        )
    if not isinstance(value, str) or not value:
        raise LiveSourceResultError(
            "locator.value must be a non-empty string", path=f"{path}.locator.value"
        )
    if len(value) > MAX_LOCATOR_VALUE_LENGTH:
        raise LiveSourceResultError(
            f"locator.value must be at most {MAX_LOCATOR_VALUE_LENGTH} characters",
            path=f"{path}.locator.value",
        )
    if any(ord(ch) < 0x20 for ch in value):
        raise LiveSourceResultError(
            "locator.value must not contain control characters",
            path=f"{path}.locator.value",
        )
    allowed = LOCATOR_KINDS_BY_SOURCE_KIND[source_kind]
    if kind not in allowed:
        raise LiveSourceResultError(
            "locator kind {!r} is not valid for source kind {!r}; allowed: {}".format(
                kind, source_kind.value, ", ".join(sorted(allowed))
            ),
            path=f"{path}.locator.kind",
        )
    return {"kind": kind, "value": value}


def validate_live_source_result(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a normalized live-source result, returning a JSON-safe dict.

    Raises :class:`LiveSourceResultError` on any violation. Fail-closed
    checks: unknown/missing fields, record type, stable source identity,
    source kind, bounded title and display text, captured/version
    metadata, the typed-locator boundary, and the live execution and
    evidence partitions — offline values are rejected so live evidence
    can never be relabeled as offline.
    """
    path = "$"
    _check_fields(raw, LIVE_SOURCE_RESULT_FIELDS, "live source result", path)
    record_type = _enum(raw.get("type"), RecordType, "type", path)
    if record_type is not RecordType.LIVE_SOURCE_RESULT:
        raise LiveSourceResultError(
            f"type must be {RecordType.LIVE_SOURCE_RESULT.value!r}, "
            f"got {record_type.value!r}",
            path=f"{path}.type",
        )
    source_kind = _enum(raw["source_kind"], SourceKind, "source_kind", path)
    execution_mode = _enum(raw["execution_mode"], ExecutionMode, "execution_mode", path)
    if execution_mode is not ExecutionMode.LIVE:
        raise LiveSourceResultError(
            "a live source result cannot claim offline execution; "
            "offline evidence uses the Phase 3/4 fixture contracts",
            path=f"{path}.execution_mode",
        )
    evidence_partition = _enum(
        raw["evidence_partition"], EvidencePartition, "evidence_partition", path
    )
    if evidence_partition is not EvidencePartition.LIVE:
        raise LiveSourceResultError(
            "a live source result cannot claim the offline evidence "
            "partition; live evidence is never mixed with offline fixtures",
            path=f"{path}.evidence_partition",
        )
    return {
        "type": RecordType.LIVE_SOURCE_RESULT.value,
        "source_id": _source_id(raw["source_id"], path),
        "source_kind": source_kind.value,
        "title": _bounded_text(raw["title"], "title", path, MAX_TITLE_LENGTH),
        "captured_at": _captured_at(raw["captured_at"], path),
        "version": _version(raw["version"], path),
        "display_text": _bounded_text(
            raw["display_text"], "display_text", path, MAX_DISPLAY_TEXT_LENGTH
        ),
        "locator": _locator(raw["locator"], source_kind, path),
        "execution_mode": ExecutionMode.LIVE.value,
        "evidence_partition": EvidencePartition.LIVE.value,
    }
