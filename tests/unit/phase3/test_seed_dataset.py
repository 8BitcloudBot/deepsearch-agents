"""Unit: seed-10 dataset loader and manifest validation (P3-2).

Covers the curated seed-10 dataset (exact count, unique and sorted case
IDs, valid split, case schema, source coverage against the corpus) and
the strict rejections: manifest/hash/count/corpus mismatch, duplicate or
unsorted case IDs, invalid split, unknown source IDs, unknown or missing
fields, non-UTF-8 text and path traversal.
"""

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.evaluation.contracts import Dataset, EvaluationCase
from benchmarks.evaluation.datasets import load_dataset
from benchmarks.evaluation.source_corpus import load_corpus

SEED_IDS = [f"seed-{i:03d}" for i in range(1, 11)]
VALID_DIFFICULTIES = {"basic", "intermediate", "advanced"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _case(case_id: str = "seed-001", **overrides) -> dict:
    case = {
        "case_id": case_id,
        "split": "seed",
        "question": f"Question for {case_id}?",
        "expected_topics": ["single-agent"],
        "allowed_source_ids": ["web-agent-frameworks-v1"],
        "difficulty": "basic",
    }
    case.update(overrides)
    return case


def _seed_lines() -> list[dict]:
    lines = []
    for i, case_id in enumerate(SEED_IDS, start=1):
        topics = (
            ["single-agent", "orchestrator-workers"]
            if i % 2
            else ["offline-evaluation"]
        )
        allowed = ["web-agent-frameworks-v1", "knowledge-evaluation-notes-v1"]
        lines.append(
            _case(
                case_id=case_id,
                question=f"Seed question {i}: compare agent orchestration approaches.",
                expected_topics=topics,
                allowed_source_ids=allowed,
                difficulty="basic" if i <= 4 else "intermediate",
            )
        )
    return lines


def _write_dataset(tmp_path: Path, entry: dict, lines: list[dict]) -> Path:
    """Write a single-entry dataset registry: ``{"datasets": [entry]}``.

    The manifest is a strict multi-dataset registry (P3-5); every helper
    wraps the entry under the ``datasets`` key so the loader exercises
    the same registry path as the versioned manifest.
    """
    root = tmp_path / "datasets"
    root.mkdir(parents=True, exist_ok=True)
    rel = entry.get("file", "seed-10.jsonl")
    fpath = root / rel
    fpath.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
        encoding="utf-8",
    )
    if "file_sha256" not in entry:
        entry["file_sha256"] = _sha256(fpath.read_bytes())
    mp = root / "manifest.json"
    mp.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
    return mp


def _valid_seed_entry() -> dict:
    """A valid seed-10 registry entry (one ``datasets`` list member)."""
    return {
        "dataset_id": "seed-10-v1",
        "schema_version": 1,
        "corpus_id": "agent-research-corpus-v1",
        "case_count": 10,
        "file": "seed-10.jsonl",
    }


class TestCuratedSeed10:
    def test_seed10_loads_exact_ten_cases(self):
        dataset = load_dataset()
        assert isinstance(dataset, Dataset)
        assert dataset.dataset_id == "seed-10-v1"
        assert dataset.schema_version == 1
        assert dataset.case_count == 10
        assert len(dataset.cases) == 10

    def test_seed10_ids_unique_and_sorted(self):
        dataset = load_dataset()
        ids = [c.case_id for c in dataset.cases]
        assert ids == SEED_IDS
        assert ids == sorted(ids)
        assert len(set(ids)) == 10

    def test_seed10_split_and_difficulty_valid(self):
        dataset = load_dataset()
        assert all(c.split == "seed" for c in dataset.cases)
        assert all(c.difficulty in VALID_DIFFICULTIES for c in dataset.cases)

    def test_seed10_case_schema(self):
        dataset = load_dataset()
        for case in dataset.cases:
            assert isinstance(case, EvaluationCase)
            assert case.question
            assert len(case.expected_topics) >= 1
            assert all(isinstance(t, str) and t for t in case.expected_topics)
            assert len(case.allowed_source_ids) >= 1
            assert all(isinstance(s, str) and s for s in case.allowed_source_ids)

    def test_seed10_allowed_sources_exist_in_corpus(self):
        corpus = load_corpus()
        corpus_ids = {s.source_id for s in corpus.sources}
        dataset = load_dataset()
        for case in dataset.cases:
            assert set(case.allowed_source_ids) <= corpus_ids, case.case_id

    def test_seed10_manifest_matches_data_files(self):
        dataset = load_dataset()
        manifest_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "data"
            / "phase3"
            / "datasets"
            / "manifest.json"
        )
        registry = json.loads(manifest_path.read_text(encoding="utf-8"))
        seed_entries = [
            entry
            for entry in registry["datasets"]
            if entry["dataset_id"] == "seed-10-v1"
        ]
        assert len(seed_entries) == 1
        seed = seed_entries[0]
        jsonl_path = manifest_path.parent / seed["file"]
        assert seed["dataset_id"] == "seed-10-v1"
        assert seed["schema_version"] == 1
        assert seed["corpus_id"] == "agent-research-corpus-v1"
        assert seed["case_count"] == 10
        assert seed["file_sha256"] == _sha256(jsonl_path.read_bytes())
        assert dataset.file_sha256 == seed["file_sha256"]
        assert dataset.corpus_id == seed["corpus_id"]


class TestDatasetRejections:
    def test_file_hash_mismatch_rejected(self, tmp_path):
        manifest = _valid_seed_entry()
        manifest["file_sha256"] = "0" * 64
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match="mismatch"):
            load_dataset(mp, corpus=load_corpus())

    def test_case_count_mismatch_rejected(self, tmp_path):
        manifest = _valid_seed_entry()
        manifest["case_count"] = 9
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match="count"):
            load_dataset(mp, corpus=load_corpus())

    def test_corpus_id_mismatch_rejected(self, tmp_path):
        manifest = _valid_seed_entry()
        manifest["corpus_id"] = "other-corpus-v9"
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match="corpus_id"):
            load_dataset(mp, corpus=load_corpus())

    def test_duplicate_case_id_rejected(self, tmp_path):
        lines = _seed_lines()
        lines[1] = dict(lines[0])
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="duplicate"):
            load_dataset(mp, corpus=load_corpus())

    def test_unsorted_case_ids_rejected(self, tmp_path):
        lines = _seed_lines()
        lines[0], lines[1] = lines[1], lines[0]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="sorted"):
            load_dataset(mp, corpus=load_corpus())

    def test_invalid_split_rejected(self, tmp_path):
        lines = [_case(split="test")]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="split"):
            load_dataset(mp, corpus=load_corpus())

    def test_split_prefix_mismatch_rejected(self, tmp_path):
        lines = [_case(case_id="dev-001")]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="split"):
            load_dataset(mp, corpus=load_corpus())

    def test_unknown_source_id_rejected(self, tmp_path):
        lines = [_case(allowed_source_ids=["does-not-exist-v1"])]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="unknown source"):
            load_dataset(mp, corpus=load_corpus())

    def test_unknown_case_field_rejected(self, tmp_path):
        lines = [_case(extra_field=True)]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), lines)
        with pytest.raises(ValueError, match="unknown field"):
            load_dataset(mp, corpus=load_corpus())

    @pytest.mark.parametrize(
        "field",
        [
            "case_id",
            "split",
            "question",
            "expected_topics",
            "allowed_source_ids",
            "difficulty",
        ],
    )
    def test_missing_case_field_rejected(self, tmp_path, field):
        line = _case()
        del line[field]
        mp = _write_dataset(tmp_path, _valid_seed_entry(), [line])
        with pytest.raises(ValueError, match=field):
            load_dataset(mp, corpus=load_corpus())

    def test_empty_expected_topics_rejected(self, tmp_path):
        mp = _write_dataset(tmp_path, _valid_seed_entry(), [_case(expected_topics=[])])
        with pytest.raises(ValueError, match="expected_topics"):
            load_dataset(mp, corpus=load_corpus())

    def test_empty_allowed_sources_rejected(self, tmp_path):
        mp = _write_dataset(
            tmp_path, _valid_seed_entry(), [_case(allowed_source_ids=[])]
        )
        with pytest.raises(ValueError, match="allowed_source_ids"):
            load_dataset(mp, corpus=load_corpus())

    def test_invalid_difficulty_rejected(self, tmp_path):
        mp = _write_dataset(tmp_path, _valid_seed_entry(), [_case(difficulty="expert")])
        with pytest.raises(ValueError, match="difficulty"):
            load_dataset(mp, corpus=load_corpus())

    def test_non_utf8_dataset_rejected(self, tmp_path):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        fpath = root / "seed-10.jsonl"
        fpath.write_bytes(b"\xff\xfe not utf-8\n")
        entry = _valid_seed_entry()
        entry["file_sha256"] = _sha256(fpath.read_bytes())
        mp = root / "manifest.json"
        mp.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
        with pytest.raises(ValueError, match="UTF-8"):
            load_dataset(mp, corpus=load_corpus())

    def test_manifest_path_traversal_rejected(self, tmp_path):
        manifest = _valid_seed_entry()
        manifest["file"] = "../escape.jsonl"
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match="escape"):
            load_dataset(mp, corpus=load_corpus())

    def test_manifest_unknown_field_rejected(self, tmp_path):
        manifest = _valid_seed_entry()
        manifest["extra"] = True
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match="unknown field"):
            load_dataset(mp, corpus=load_corpus())

    @pytest.mark.parametrize(
        "field",
        ["dataset_id", "schema_version", "corpus_id", "case_count", "file"],
    )
    def test_manifest_missing_field_rejected(self, tmp_path, field):
        manifest = _valid_seed_entry()
        del manifest[field]
        mp = _write_dataset(tmp_path, manifest, _seed_lines())
        with pytest.raises(ValueError, match=field):
            load_dataset(mp, corpus=load_corpus())

    def test_manifest_missing_file_sha256_rejected(self, tmp_path):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        fpath = root / "seed-10.jsonl"
        fpath.write_text(
            "".join(json.dumps(line) + "\n" for line in _seed_lines()),
            encoding="utf-8",
        )
        entry = _valid_seed_entry()
        mp = root / "manifest.json"
        mp.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
        with pytest.raises(ValueError, match="file_sha256"):
            load_dataset(mp, corpus=load_corpus())

    def test_invalid_json_line_rejected(self, tmp_path):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        fpath = root / "seed-10.jsonl"
        fpath.write_text("{not json}\n", encoding="utf-8")
        entry = _valid_seed_entry()
        entry["file_sha256"] = _sha256(fpath.read_bytes())
        mp = root / "manifest.json"
        mp.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
        with pytest.raises(ValueError, match="JSON"):
            load_dataset(mp, corpus=load_corpus())

    def test_non_object_line_rejected(self, tmp_path):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        fpath = root / "seed-10.jsonl"
        fpath.write_text("[1, 2]\n", encoding="utf-8")
        entry = _valid_seed_entry()
        entry["file_sha256"] = _sha256(fpath.read_bytes())
        mp = root / "manifest.json"
        mp.write_text(json.dumps({"datasets": [entry]}), encoding="utf-8")
        with pytest.raises(ValueError, match="object"):
            load_dataset(mp, corpus=load_corpus())


class TestDatasetManifestUtf8:
    """The dataset manifest must be strict UTF-8 text.

    ``json.loads`` auto-detects UTF-16/UTF-32 (and strips a UTF-8 BOM)
    from bytes, which would silently violate the UTF-8-only contract, so
    the loader must reject anything but plain UTF-8.
    """

    @pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
    def test_non_utf8_dataset_manifest_rejected(self, tmp_path, encoding):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.json").write_bytes(
            json.dumps({"datasets": [_valid_seed_entry()]}).encode(encoding)
        )
        with pytest.raises(ValueError, match="UTF-8"):
            load_dataset(root / "manifest.json", corpus=load_corpus())

    def test_bom_dataset_manifest_rejected(self, tmp_path):
        root = tmp_path / "datasets"
        root.mkdir(parents=True, exist_ok=True)
        (root / "manifest.json").write_bytes(
            b"\xef\xbb\xbf"
            + json.dumps({"datasets": [_valid_seed_entry()]}).encode("utf-8")
        )
        with pytest.raises(ValueError, match="UTF-8"):
            load_dataset(root / "manifest.json", corpus=load_corpus())
