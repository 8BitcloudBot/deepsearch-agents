import json
from pathlib import Path

import pytest

from app.knowledge.contracts import KnowledgeDocumentChunk
from scripts.build_showcase_knowledge import build_manifest


def test_candidate_review_records_nine_candidates_and_selected_sources() -> None:
    root = Path(__file__).resolve().parents[3]
    candidates = json.loads(
        (root / "data/knowledge/showcase-v1/candidates.json").read_text(
            encoding="utf-8"
        )
    )
    sources = json.loads(
        (root / "data/knowledge/showcase-v1/sources.json").read_text(encoding="utf-8")
    )

    assert candidates["schema_version"] == "1.0.0"
    assert candidates["retrieved_at"] == "2026-08-12"
    assert len(candidates["candidates"]) == 9
    required = {
        "candidate_id",
        "title",
        "source_url",
        "publisher",
        "source_version",
        "retrieved_at",
        "license",
        "estimated_normalized_characters",
        "estimated_chunks",
        "selection_value",
        "intended_questions",
        "recommended",
        "decision_reason",
    }
    assert all(set(candidate) == required for candidate in candidates["candidates"])
    assert all(
        candidate["source_url"].startswith("https://")
        and candidate["estimated_normalized_characters"] > 0
        and candidate["estimated_chunks"] > 0
        and candidate["intended_questions"]
        for candidate in candidates["candidates"]
    )
    selected = {
        candidate["candidate_id"]
        for candidate in candidates["candidates"]
        if candidate["recommended"]
    }
    assert selected == {document["document_id"] for document in sources["documents"]}


def test_build_manifest_creates_stable_semantic_chunks(tmp_path: Path) -> None:
    source = tmp_path / "example.md"
    source.write_text(
        "# Example\n\nIntro paragraph.\n\n## Local mode\n\n"
        "Path mode persists vectors between process runs.\n\n"
        "A second paragraph stays in the same section.\n",
        encoding="utf-8",
    )
    catalog = {
        "collection_id": "deepsearch-showcase-v1",
        "documents": [
            {
                "document_id": "example-document",
                "title": "Example",
                "source_version": "1.0.0+abc123",
                "source_url": "https://example.test/README.md",
                "local_sources": ["example.md"],
            }
        ],
    }

    first = build_manifest(catalog, source_root=tmp_path)
    second = build_manifest(catalog, source_root=tmp_path)

    assert first == second
    assert first["schema_version"] == "1.0.0"
    assert first["chunking_version"] == "semantic-markdown-v1"
    chunks = first["documents"][0]["chunks"]
    assert [chunk["chunk_id"] for chunk in chunks] == [
        "example-document-0001",
        "example-document-0002",
    ]
    assert chunks[1]["section_path"] == "Example > Local mode"
    assert chunks[1]["source_uri"] == "https://example.test/README.md"
    KnowledgeDocumentChunk(**chunks[1])
    assert "second paragraph" in chunks[1]["content"]


def test_build_manifest_rejects_missing_or_escaping_local_sources(
    tmp_path: Path,
) -> None:
    base = {
        "collection_id": "deepsearch-showcase-v1",
        "documents": [
            {
                "document_id": "example-document",
                "title": "Example",
                "source_version": "1.0.0+abc123",
                "source_url": "https://example.test/README.md",
                "local_sources": ["missing.md"],
            }
        ],
    }

    with pytest.raises(ValueError, match="source"):
        build_manifest(base, source_root=tmp_path)

    base["documents"][0]["local_sources"] = ["../outside.md"]
    with pytest.raises(ValueError, match="source"):
        build_manifest(base, source_root=tmp_path)


def test_build_manifest_rejects_source_hash_mismatch(tmp_path: Path) -> None:
    (tmp_path / "example.md").write_text("# Example\n\nContent.\n", encoding="utf-8")
    catalog = {
        "collection_id": "deepsearch-showcase-v1",
        "documents": [
            {
                "document_id": "example-document",
                "title": "Example",
                "source_version": "1.0.0+abc123",
                "source_url": "https://example.test/README.md",
                "content_sha256": "0" * 64,
                "local_sources": ["example.md"],
            }
        ],
    }

    with pytest.raises(ValueError, match="hash"):
        build_manifest(catalog, source_root=tmp_path)
