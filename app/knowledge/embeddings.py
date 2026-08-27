"""Embedding adapters; production models stay lazy and offline tests use a fake."""

from __future__ import annotations

import hashlib
from typing import Any

from app.knowledge.contracts import EmbeddingDescriptor


class FakeEmbeddingAdapter:
    """Deterministic, dependency-free embedder for fixtures and tests."""

    def __init__(self, dimension: int = 8) -> None:
        self.descriptor = EmbeddingDescriptor(
            provider="fake",
            model="deterministic-fixture",
            version="1.0.0",
            dimension=dimension,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        dimension = self.descriptor.dimension
        return [
            ((digest[index % len(digest)] / 255.0) * 2.0) - 1.0
            for index in range(dimension)
        ]


class FastEmbedEmbeddingAdapter:
    """Lazy FastEmbed seam.

    Constructing configuration never loads or downloads a model.
    """

    def __init__(
        self,
        *,
        model: str,
        version: str,
        dimension: int,
        cache_dir: str | None = None,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        self.descriptor = EmbeddingDescriptor(
            provider="fastembed",
            model=model,
            version=version,
            dimension=dimension,
            query_prefix=query_prefix,
            document_prefix=document_prefix,
        )
        self._cache_dir = cache_dir
        self._model: Any = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            kwargs: dict[str, object] = {"model_name": self.descriptor.model}
            if self._cache_dir is not None:
                kwargs["cache_dir"] = self._cache_dir
            self._model = TextEmbedding(**kwargs)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        values = [self.descriptor.document_prefix + text for text in texts]
        return [vector.tolist() for vector in self._load().embed(values)]

    def embed_query(self, text: str) -> list[float]:
        value = self.descriptor.query_prefix + text
        return next(self._load().query_embed(value)).tolist()
