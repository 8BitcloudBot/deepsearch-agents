import builtins

import pytest

from app.knowledge.embeddings import FakeEmbeddingAdapter, FastEmbedEmbeddingAdapter


def test_fake_embedding_is_deterministic_and_has_declared_dimension() -> None:
    embedder = FakeEmbeddingAdapter(dimension=8)

    first = embedder.embed_query("knowledge fixture")
    second = embedder.embed_query("knowledge fixture")

    assert first == second
    assert len(first) == embedder.descriptor.dimension == 8
    assert embedder.embed_documents(["one", "two"]) == [
        embedder.embed_query("one"),
        embedder.embed_query("two"),
    ]


def test_fastembed_adapter_is_lazy_until_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported: list[str] = []
    original_import = builtins.__import__

    def guarded_import(name: str, *args, **kwargs):
        if name == "fastembed" or name.startswith("fastembed."):
            imported.append(name)
            raise AssertionError("fastembed imported during configuration")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    adapter = FastEmbedEmbeddingAdapter(
        model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        version="pinned",
        dimension=384,
    )

    assert (
        adapter.descriptor.model
        == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    assert imported == []
