import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.knowledge.index_manifest import load_knowledge_manifest


def manifest() -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "collection_id": "deepsearch-showcase-v1",
        "chunking_version": "manual-v1",
        "documents": [
            {
                "document_id": "example-document",
                "title": "Example document",
                "version": "1.0.0",
                "chunks": [
                    {
                        "chunk_id": "chunk-0001",
                        "content": "Non-sensitive example content.",
                        "section_path": "Overview",
                        "source_uri": "https://example.test/document",
                    }
                ],
            }
        ],
    }


def write_manifest(tmp_path: Path, value: object) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_load_knowledge_manifest_returns_validated_documents(tmp_path: Path) -> None:
    collection, chunking, documents = load_knowledge_manifest(
        write_manifest(tmp_path, manifest())
    )

    assert collection == "deepsearch-showcase-v1"
    assert chunking == "manual-v1"
    assert len(documents) == 1
    assert documents[0].collection_id == collection
    assert documents[0].document_id == "example-document"
    assert documents[0].chunks[0].chunk_id == "chunk-0001"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(extra="not-allowed"),
        lambda value: value.pop("collection_id"),
        lambda value: value.update(schema_version="2.0.0"),
        lambda value: value.update(documents=[]),
        lambda value: value["documents"][0].update(extra="not-allowed"),
        lambda value: value["documents"][0].pop("version"),
        lambda value: value["documents"][0].update(chunks=[]),
        lambda value: value["documents"][0]["chunks"][0].update(extra="not-allowed"),
        lambda value: value["documents"][0]["chunks"][0].pop("content"),
    ],
)
def test_manifest_rejects_wrong_schema_or_field_shape(tmp_path: Path, mutation) -> None:
    value = manifest()
    mutation(value)

    with pytest.raises(ValueError, match="manifest"):
        load_knowledge_manifest(write_manifest(tmp_path, value))


def test_manifest_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    value = manifest()
    value["documents"].append(deepcopy(value["documents"][0]))

    with pytest.raises(ValueError, match="document"):
        load_knowledge_manifest(write_manifest(tmp_path, value))


def test_manifest_rejects_duplicate_chunk_ids(tmp_path: Path) -> None:
    value = manifest()
    value["documents"][0]["chunks"].append(deepcopy(value["documents"][0]["chunks"][0]))

    with pytest.raises(ValueError, match="chunk"):
        load_knowledge_manifest(write_manifest(tmp_path, value))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(collection_id="../private"),
        lambda value: value["documents"][0].update(document_id="../../document"),
        lambda value: value["documents"][0]["chunks"][0].update(
            chunk_id="/Users/private/chunk"
        ),
        lambda value: value["documents"][0]["chunks"][0].update(content="x" * 65537),
        lambda value: value["documents"][0]["chunks"][0].update(
            source_uri="file:///Users/private/document"
        ),
    ],
)
def test_manifest_rejects_unsafe_metadata(tmp_path: Path, mutation) -> None:
    value = manifest()
    mutation(value)

    with pytest.raises(ValueError):
        load_knowledge_manifest(write_manifest(tmp_path, value))


@pytest.mark.parametrize("value", ["not-json", "[]", "null"])
def test_manifest_rejects_invalid_json_root(tmp_path: Path, value: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(value, encoding="utf-8")

    with pytest.raises(ValueError, match="manifest"):
        load_knowledge_manifest(path)
