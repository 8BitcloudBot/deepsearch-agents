from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "index_knowledge.py"


def write_manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
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
        ),
        encoding="utf-8",
    )
    return path


def run_cli(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_only_is_offline_and_does_not_create_runtime_directories(
    tmp_path: Path,
) -> None:
    manifest = write_manifest(tmp_path)

    result = run_cli(
        tmp_path,
        "--manifest",
        str(manifest),
        "--index-path",
        ".data/knowledge-index",
        "--collection",
        "deepsearch-showcase-v1",
        "--validate-only",
    )

    assert result.returncode == 0
    assert "collection=deepsearch-showcase-v1" in result.stdout
    assert "documents=1" in result.stdout
    assert "chunks=1" in result.stdout
    assert "fingerprint=" in result.stdout
    assert "indexed=0" in result.stdout
    assert "skipped=0" in result.stdout
    assert "Non-sensitive example content" not in result.stdout
    assert str(tmp_path) not in result.stdout
    assert not (tmp_path / ".data").exists()
    assert not (tmp_path / ".cache").exists()


def test_validate_only_does_not_import_embedding_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = write_manifest(tmp_path)
    monkeypatch.setitem(sys.modules, "app.knowledge.embeddings", None)
    spec = importlib.util.spec_from_file_location("index_knowledge_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)

    result = module.main(
        [
            "--manifest",
            str(manifest),
            "--index-path",
            ".data/knowledge-index",
            "--collection",
            "deepsearch-showcase-v1",
            "--validate-only",
        ]
    )

    assert result == 0
    assert not (tmp_path / ".data").exists()
    assert not (tmp_path / ".cache").exists()


def test_index_mode_calls_local_index_once_with_validated_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = write_manifest(tmp_path)
    calls: list[tuple[Path, tuple[object, ...]]] = []

    class FakeEmbedder:
        def __init__(self, **kwargs):
            from app.knowledge.contracts import EmbeddingDescriptor

            self.descriptor = EmbeddingDescriptor(
                provider="fastembed",
                model=kwargs["model"],
                version=kwargs["version"],
                dimension=kwargs["dimension"],
            )

    class FakeIndex:
        def __init__(self, path, spec, embedder):
            self.path = path
            self.spec = spec

        def index_documents(self, documents):
            calls.append((self.path, documents))
            return SimpleNamespace(
                collection_id=self.spec.collection_id,
                index_fingerprint=self.spec.index_fingerprint,
                indexed_chunks=1,
                skipped_chunks=0,
            )

    embeddings = ModuleType("app.knowledge.embeddings")
    embeddings.FastEmbedEmbeddingAdapter = FakeEmbedder
    qdrant = ModuleType("app.knowledge.qdrant_local")
    qdrant.QdrantLocalKnowledgeIndex = FakeIndex
    monkeypatch.setitem(sys.modules, "app.knowledge.embeddings", embeddings)
    monkeypatch.setitem(sys.modules, "app.knowledge.qdrant_local", qdrant)
    spec = importlib.util.spec_from_file_location("index_knowledge_index_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)

    result = module.main(
        [
            "--manifest",
            str(manifest),
            "--index-path",
            ".data/knowledge-index",
            "--collection",
            "deepsearch-showcase-v1",
        ]
    )

    assert result == 0
    assert len(calls) == 1
    assert calls[0][0] == (tmp_path / ".data/knowledge-index").resolve()
    assert calls[0][1][0].document_id == "example-document"
    output = capsys.readouterr().out
    assert "indexed=1" in output
    assert "skipped=0" in output
    assert str(tmp_path) not in output


@pytest.mark.parametrize(
    ("collection", "index_path"),
    [
        ("another-collection", ".data/knowledge-index"),
        ("deepsearch-showcase-v1", "/tmp/private-index"),
        ("deepsearch-showcase-v1", "../private-index"),
    ],
)
def test_cli_rejects_collection_mismatch_and_unsafe_index_paths(
    tmp_path: Path, collection: str, index_path: str
) -> None:
    manifest = write_manifest(tmp_path)

    result = run_cli(
        tmp_path,
        "--manifest",
        str(manifest),
        "--index-path",
        index_path,
        "--collection",
        collection,
        "--validate-only",
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "invalid" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert not (tmp_path / ".data").exists()
