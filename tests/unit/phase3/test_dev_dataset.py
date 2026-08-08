"""Unit: dev-40 dataset and the strict multi-dataset registry (P3-5).

The versioned manifest is a registry of frozen datasets (seed-10-v1 and
dev-40-v1). These tests cover: the curated dev-40 dataset (exact count,
unique and sorted case IDs dev-001..dev-040, split, difficulty, case
schema, source coverage against the corpus, manifest hash), deterministic
registry selection (``load_dataset()`` still defaults to seed-10-v1;
``load_dataset_by_name`` accepts seed-10|seed-10-v1|dev-40|dev-40-v1),
seed-10 immutability (frozen SHA-256), and strict registry rejections
(unknown names, duplicate entries, unknown top-level/entry fields,
non-object manifest, missing/empty registry, missing default dataset).
"""

import hashlib
import json
from pathlib import Path

import pytest

from app.evaluation.contracts import Dataset, EvaluationCase
from app.evaluation.datasets import (
    DATASET_ALIASES,
    DEFAULT_DATASET_ID,
    load_dataset,
    load_dataset_by_name,
)
from app.research.corpus import load_corpus

SEED_SHA256 = "a902aba483f89285b02792369963ce5edb35f3460abfdcc1b7f712b0e8cf1055"
DEV_IDS = [f"dev-{i:03d}" for i in range(1, 41)]
VALID_DIFFICULTIES = {"basic", "intermediate", "advanced"}
_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "phase3"
    / "datasets"
    / "manifest.json"
)
# Content that must never appear in curated case data.
_FORBIDDEN = (
    "api_key",
    "apikey",
    "password",
    "secret",
    "bearer ",
    "/Users/",
    "/tmp/",
    "/private/",
    "```",
    "C:\\",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dev_line(i: int, **overrides) -> dict:
    case = {
        "case_id": f"dev-{i:03d}",
        "split": "dev",
        "question": f"Curated dev question {i} about agent research evaluation?",
        "expected_topics": ["single-agent"],
        "allowed_source_ids": ["web-agent-frameworks-v1"],
        "difficulty": "basic",
    }
    case.update(overrides)
    return case


def _dev_lines(count: int = 40) -> list[dict]:
    return [_dev_line(i) for i in range(1, count + 1)]


def _write_registry(
    tmp_path: Path, entries: list[dict], files: dict[str, list[dict]]
) -> Path:
    """Write ``tmp_path/datasets/{files}`` plus a registry manifest.

    ``files`` maps a relative JSONL name to its case lines; a missing
    ``file_sha256`` on an entry is computed from the written bytes.
    """
    root = tmp_path / "datasets"
    root.mkdir(parents=True, exist_ok=True)
    for rel, lines in files.items():
        (root / rel).write_text(
            "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
            encoding="utf-8",
        )
    for entry in entries:
        if "file_sha256" not in entry:
            entry["file_sha256"] = _sha256((root / entry["file"]).read_bytes())
    mp = root / "manifest.json"
    mp.write_text(json.dumps({"datasets": entries}), encoding="utf-8")
    return mp


def _write_manifest_json(tmp_path: Path, payload) -> Path:
    root = tmp_path / "datasets"
    root.mkdir(parents=True, exist_ok=True)
    mp = root / "manifest.json"
    mp.write_text(json.dumps(payload), encoding="utf-8")
    return mp


def _dev_entry(**overrides) -> dict:
    entry = {
        "dataset_id": "dev-40-v1",
        "schema_version": 1,
        "corpus_id": "agent-research-corpus-v1",
        "case_count": 40,
        "file": "dev-40.jsonl",
    }
    entry.update(overrides)
    return entry


def _seed_entry(**overrides) -> dict:
    entry = {
        "dataset_id": "seed-10-v1",
        "schema_version": 1,
        "corpus_id": "agent-research-corpus-v1",
        "case_count": 10,
        "file": "seed-10.jsonl",
    }
    entry.update(overrides)
    return entry


class TestCuratedDev40:
    def test_dev40_loads_via_alias_and_full_id(self):
        for name in ("dev-40", "dev-40-v1"):
            dataset = load_dataset_by_name(name)
            assert isinstance(dataset, Dataset)
            assert dataset.dataset_id == "dev-40-v1"
            assert dataset.schema_version == 1
            assert dataset.corpus_id == "agent-research-corpus-v1"
            assert dataset.case_count == 40
            assert len(dataset.cases) == 40

    def test_dev40_ids_unique_and_sorted(self):
        dataset = load_dataset_by_name("dev-40")
        ids = [case.case_id for case in dataset.cases]
        assert ids == DEV_IDS
        assert ids == sorted(ids)
        assert len(set(ids)) == 40

    def test_dev40_split_and_difficulty_valid(self):
        dataset = load_dataset_by_name("dev-40")
        assert all(case.split == "dev" for case in dataset.cases)
        assert all(case.difficulty in VALID_DIFFICULTIES for case in dataset.cases)

    def test_dev40_case_schema(self):
        dataset = load_dataset_by_name("dev-40")
        for case in dataset.cases:
            assert isinstance(case, EvaluationCase)
            assert case.question
            assert len(case.expected_topics) >= 1
            assert all(isinstance(t, str) and t for t in case.expected_topics)
            assert len(case.allowed_source_ids) >= 1
            assert all(isinstance(s, str) and s for s in case.allowed_source_ids)

    def test_dev40_allowed_sources_exist_in_corpus(self):
        corpus = load_corpus()
        corpus_ids = {source.source_id for source in corpus.sources}
        dataset = load_dataset_by_name("dev-40")
        for case in dataset.cases:
            assert set(case.allowed_source_ids) <= corpus_ids, case.case_id

    def test_dev40_manifest_hash_matches_data_file(self):
        dataset = load_dataset_by_name("dev-40")
        data = (_MANIFEST_PATH.parent / "dev-40.jsonl").read_bytes()
        assert dataset.file_sha256 == _sha256(data)
        registry = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        dev_entries = [
            entry
            for entry in registry["datasets"]
            if entry["dataset_id"] == "dev-40-v1"
        ]
        assert len(dev_entries) == 1
        assert dev_entries[0]["file_sha256"] == _sha256(data)
        assert dev_entries[0]["case_count"] == 40

    def test_dev40_questions_are_varied(self):
        dataset = load_dataset_by_name("dev-40")
        questions = [case.question for case in dataset.cases]
        assert len(set(questions)) == 40

    def test_dev40_contains_no_forbidden_content(self):
        dataset = load_dataset_by_name("dev-40")
        for case in dataset.cases:
            text = " ".join(
                (case.question, *case.expected_topics, *case.allowed_source_ids)
            ).lower()
            for marker in _FORBIDDEN:
                assert marker not in text, f"{case.case_id}: {marker!r}"


class TestRegistrySelection:
    def test_default_load_dataset_is_seed10(self):
        dataset = load_dataset()
        assert dataset.dataset_id == DEFAULT_DATASET_ID == "seed-10-v1"
        assert dataset.case_count == 10

    def test_seed_aliases_still_select_seed10(self):
        for name in ("seed-10", "seed-10-v1"):
            dataset = load_dataset_by_name(name)
            assert dataset.dataset_id == "seed-10-v1"

    def test_seed10_is_immutable_frozen_hash(self):
        dataset = load_dataset_by_name("seed-10")
        assert dataset.file_sha256 == SEED_SHA256
        registry = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        seed_entries = [
            entry
            for entry in registry["datasets"]
            if entry["dataset_id"] == "seed-10-v1"
        ]
        assert len(seed_entries) == 1
        assert seed_entries[0]["file_sha256"] == SEED_SHA256
        assert seed_entries[0]["case_count"] == 10

    def test_registry_contains_exactly_seed_and_dev(self):
        registry = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        ids = sorted(entry["dataset_id"] for entry in registry["datasets"])
        assert ids == ["dev-40-v1", "seed-10-v1"]

    def test_cli_aliases_map_to_frozen_ids(self):
        assert DATASET_ALIASES == {
            "seed-10": "seed-10-v1",
            "dev-40": "dev-40-v1",
        }


class TestRegistryRejections:
    def test_unknown_dataset_name_rejected(self):
        for name in ("dev-999", "dev-41", "seed-09", "seed-11"):
            with pytest.raises(ValueError, match="unknown dataset"):
                load_dataset_by_name(name)

    def test_duplicate_registry_entry_rejected(self, tmp_path):
        entry = _dev_entry()
        mp = _write_registry(
            tmp_path, [entry, dict(entry)], {"dev-40.jsonl": _dev_lines()}
        )
        with pytest.raises(ValueError, match="duplicate"):
            load_dataset(mp, corpus=load_corpus())

    def test_unknown_top_level_manifest_field_rejected(self, tmp_path):
        entry = _dev_entry()
        # _write_registry mutates the entry in place to add file_sha256.
        _write_registry(tmp_path, [entry], {"dev-40.jsonl": _dev_lines()})
        payload = {"datasets": [entry], "extra": True}
        mp = _write_manifest_json(tmp_path, payload)
        with pytest.raises(ValueError, match="unknown field"):
            load_dataset(mp, corpus=load_corpus())

    def test_unknown_entry_field_rejected(self, tmp_path):
        entry = _dev_entry(extra=True)
        mp = _write_registry(tmp_path, [entry], {"dev-40.jsonl": _dev_lines()})
        with pytest.raises(ValueError, match="unknown field"):
            load_dataset(mp, corpus=load_corpus())

    def test_non_object_manifest_rejected(self, tmp_path):
        mp = _write_manifest_json(tmp_path, [{"datasets": []}])
        with pytest.raises(ValueError, match="must be a JSON object"):
            load_dataset(mp, corpus=load_corpus())

    def test_missing_datasets_key_rejected(self, tmp_path):
        mp = _write_manifest_json(tmp_path, {})
        with pytest.raises(ValueError, match="datasets"):
            load_dataset(mp, corpus=load_corpus())

    def test_empty_registry_rejected(self, tmp_path):
        mp = _write_manifest_json(tmp_path, {"datasets": []})
        with pytest.raises(ValueError, match="datasets"):
            load_dataset(mp, corpus=load_corpus())

    def test_registry_without_default_dataset_rejected(self, tmp_path):
        mp = _write_registry(
            tmp_path,
            [_dev_entry()],
            {"dev-40.jsonl": _dev_lines()},
        )
        with pytest.raises(ValueError, match="seed-10-v1"):
            load_dataset(mp, corpus=load_corpus())
