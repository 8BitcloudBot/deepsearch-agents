"""Run the credential-free Phase 9 portfolio demonstration on loopback."""

from __future__ import annotations

import argparse
import ipaddress
from pathlib import Path

import uvicorn

from examples.portfolio_demo.app import create_demo_app
from examples.portfolio_demo.runtime import DEMO_SCENARIOS

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def create_formal_knowledge_retriever(root: Path):
    from app.knowledge.contracts import KnowledgeIndexSpec
    from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
    from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

    embedder = FastEmbedEmbeddingAdapter(
        model=MODEL,
        version="0.8.0",
        dimension=384,
        cache_dir=str((root / ".cache" / "fastembed").resolve()),
    )
    spec = KnowledgeIndexSpec(
        collection_id="deepsearch-showcase-v1",
        embedding=embedder.descriptor,
        distance="cosine",
        chunking_version="semantic-markdown-v1",
    )
    index_path = root / ".data" / "knowledge-index"
    if not (index_path / "deepsearch-knowledge-manifest.json").is_file():
        raise ValueError("formal knowledge index is unavailable; build it first")
    return QdrantLocalKnowledgeIndex(index_path, spec, embedder, min_score=0.40)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=DEMO_SCENARIOS, default="success")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def validate_server_address(host: str, port: int) -> tuple[str, int]:
    address = ipaddress.ip_address(host)
    if not address.is_loopback:
        raise ValueError("portfolio demo host must be a loopback address")
    if not 1 <= port <= 65535:
        raise ValueError("portfolio demo port must be between 1 and 65535")
    return host, port


def main() -> None:
    args = parse_args()
    try:
        host, port = validate_server_address(args.host, args.port)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    knowledge_retriever = None
    if args.scenario == "formal-knowledge":
        try:
            knowledge_retriever = create_formal_knowledge_retriever(Path.cwd())
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    uvicorn.run(
        create_demo_app(args.scenario, knowledge_retriever=knowledge_retriever),
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
