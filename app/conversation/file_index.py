"""Per-conversation Qdrant index for uploaded session files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from app.knowledge.contracts import (
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    KnowledgeIndexSpec,
)
from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex


def _chunks(content: str) -> tuple[KnowledgeDocumentChunk, ...]:
    parts = [
        part.strip()
        for part in re.split(r"\n\s*\n|(?=^#{1,6} )", content, flags=re.MULTILINE)
        if part.strip()
    ]
    values: list[KnowledgeDocumentChunk] = []
    for index, part in enumerate(parts, 1):
        digest = hashlib.sha256(part.encode("utf-8")).hexdigest()[:16]
        values.append(
            KnowledgeDocumentChunk(
                chunk_id=f"section-{index:04d}-{digest}",
                content=part,
                section_path=f"section-{index}",
            )
        )
    return tuple(values)


class SessionFileIndex:
    """Index files inside a user/conversation namespace.

    The embedder is injected so startup stays provider-lazy and tests do not
    download a model. Every namespace has its own Qdrant Local path.
    """

    def __init__(self, root: str | Path, embedder: Any) -> None:
        self._root = Path(root)
        self._embedder = embedder
        self._indexes: dict[tuple[str, str], QdrantLocalKnowledgeIndex] = {}

    def _index(self, user_id: str, conversation_id: str) -> QdrantLocalKnowledgeIndex:
        key = (user_id, conversation_id)
        if key not in self._indexes:
            spec = KnowledgeIndexSpec(
                collection_id="session_files",
                embedding=self._embedder.descriptor,
                distance="cosine",
                chunking_version="semantic-markdown-v1",
            )
            path = self._root / user_id / conversation_id
            self._indexes[key] = QdrantLocalKnowledgeIndex(path, spec, self._embedder)
        return self._indexes[key]

    def index_attachment(
        self,
        user_id: str,
        conversation_id: str,
        attachment_id: str,
        title: str,
        content: str,
    ):
        document = KnowledgeDocument(
            collection_id="session_files",
            document_id=attachment_id,
            title=title,
            version="1.0.0",
            chunks=_chunks(content),
        )
        return self._index(user_id, conversation_id).index_documents((document,))

    def index_attachment_path(
        self,
        user_id: str,
        conversation_id: str,
        attachment_id: str,
        title: str,
        path: str | Path,
    ):
        return self.index_attachment(
            user_id,
            conversation_id,
            attachment_id,
            title,
            read_supported_file(Path(path)),
        )

    def search(
        self,
        user_id: str,
        conversation_id: str,
        attachment_ids: tuple[str, ...],
        query: str,
        *,
        limit: int = 10,
    ):
        if not attachment_ids:
            return ()
        try:
            return self._index(user_id, conversation_id).search(
                query, limit=min(limit, 20), document_ids=attachment_ids
            )
        except Exception:
            return ()

    def remove_attachment(
        self, user_id: str, conversation_id: str, attachment_id: str
    ) -> None:
        try:
            self._index(user_id, conversation_id).delete_documents((attachment_id,))
        except Exception:
            return


def read_supported_file(path: Path) -> str:
    extension = path.suffix.casefold()
    if extension in {".txt", ".md"}:
        return path.read_text(encoding="utf-8")
    from app.tools.files import read_docx_file, read_pdf_file, read_xlsx_file

    readers = {
        ".pdf": read_pdf_file,
        ".docx": read_docx_file,
        ".xlsx": read_xlsx_file,
    }
    try:
        return readers[extension](path)
    except KeyError as exc:
        raise ValueError("unsupported attachment") from exc
