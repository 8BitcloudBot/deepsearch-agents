"""Deterministic offline citation evaluation report (P4-4).

``build_report`` assembles the three required homogeneous partitions
(``rule/offline``, ``semantic/mock``, ``semantic/real``) into one versioned
report whose rows and fingerprints are byte-identical across runs except for
the volatile ``report_id`` and ``generated_at`` fields (which are excluded
from ``report_fingerprint``).

Provenance binds the report to the frozen dataset/corpus manifests: dataset
id and file hash, corpus id, fixture fingerprint, and the Git commit. The
report never mixes modes or pipelines: ``build_report`` rejects any partition
set that is not exactly the three required partition ids.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.citations.metrics import PartitionMetrics
from app.citations.semantic import canonical_sha256

REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_FINGERPRINT_ALGORITHM = "sha256"
RUNNER_NAME = "evaluate_citations"
REQUIRED_PARTITION_IDS = ("rule/offline", "semantic/mock", "semantic/real")

_DATASET_FILE_SUFFIX = ".jsonl"


def git_revision() -> str:
    """The current Git commit hex, or ``"unknown"`` when unavailable."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    commit = proc.stdout.strip()
    if proc.returncode != 0 or not commit:
        return "unknown"
    return commit


def report_provenance(
    *,
    fixture_manifest: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
    sources_manifest: Mapping[str, Any],
    git_commit: str,
) -> dict[str, Any]:
    """Deterministic provenance bound to the frozen manifests."""
    fixture = fixture_manifest["fixture"]
    fixture_name = fixture["name"]
    entries = dataset_manifest.get("datasets", [])
    matches = [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and entry.get("file") == f"{fixture_name}{_DATASET_FILE_SUFFIX}"
    ]
    if not matches:
        raise ValueError(f"dataset manifest has no entry for fixture {fixture_name!r}")
    dataset = matches[0]
    return {
        "dataset_id": dataset["dataset_id"],
        "dataset_file_sha256": dataset["file_sha256"],
        "case_count": dataset["case_count"],
        "corpus_id": sources_manifest["corpus_id"],
        "fixture_fingerprint": fixture["fingerprint"],
        "fixture_fingerprint_algorithm": fixture["fingerprint_algorithm"],
        "git_commit": git_commit,
        "runner": {"name": RUNNER_NAME, "version": REPORT_SCHEMA_VERSION},
    }


def build_report(
    *,
    partitions: Sequence[PartitionMetrics],
    fixture_manifest: Mapping[str, Any],
    dataset_manifest: Mapping[str, Any],
    sources_manifest: Mapping[str, Any],
    git_commit: str | None = None,
    report_id: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble a deterministic, versioned evaluation report.

    ``partitions`` must be exactly the three required homogeneous partitions;
    anything else (missing, duplicate, or unknown partition ids) raises
    :class:`ValueError`. ``report_id``/``generated_at`` default to a fresh
    uuid and UTC timestamp; both are excluded from ``report_fingerprint``.
    """
    partition_map = {
        partition.partition_id: partition.to_dict() for partition in partitions
    }
    if len(partition_map) != len(partitions):
        raise ValueError("duplicate partition id in report partitions")
    if set(partition_map) != set(REQUIRED_PARTITION_IDS):
        raise ValueError(
            "report must contain exactly the required partitions "
            f"{', '.join(REQUIRED_PARTITION_IDS)}; got "
            f"{', '.join(sorted(partition_map)) or 'none'}"
        )
    if git_commit is None:
        git_commit = git_revision()
    if report_id is None:
        report_id = uuid.uuid4().hex
    if generated_at is None:
        generated_at = datetime.now(UTC).isoformat()

    provenance = report_provenance(
        fixture_manifest=fixture_manifest,
        dataset_manifest=dataset_manifest,
        sources_manifest=sources_manifest,
        git_commit=git_commit,
    )
    payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "provenance": provenance,
        "partitions": partition_map,
    }
    return {
        "report_id": report_id,
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "provenance": provenance,
        "partitions": partition_map,
        "report_fingerprint": canonical_sha256(payload),
    }


def serialize_json(value: Any) -> str:
    """Deterministic canonical JSON text (sorted keys, compact separators)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "REPORT_FINGERPRINT_ALGORITHM",
    "REPORT_SCHEMA_VERSION",
    "REQUIRED_PARTITION_IDS",
    "RUNNER_NAME",
    "build_report",
    "git_revision",
    "report_provenance",
    "serialize_json",
]
