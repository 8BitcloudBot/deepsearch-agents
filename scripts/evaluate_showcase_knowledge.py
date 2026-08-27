#!/usr/bin/env python3
"""Run the fixed lightweight acceptance set against the local knowledge index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.knowledge.contracts import (  # noqa: E402
    EmbeddingDescriptor,
    KnowledgeIndexSpec,
    resolve_knowledge_index_path,
)

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_VERSION = "0.8.0"
DIMENSION = 384
CHUNKING_VERSION = "semantic-markdown-v1"
MIN_SCORE = 0.40
_QUESTION_FIELDS = frozenset(
    {
        "question_id",
        "category",
        "query",
        "expected_document_ids",
        "expected_chunk_ids",
        "expected_sections",
        "expected_no_evidence",
        "rationale",
    }
)


def _strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"question {label} is invalid")
    return value


def _validated_questions(raw: dict[str, Any]) -> tuple[str, int, list[dict[str, Any]]]:
    if set(raw) != {"schema_version", "collection_id", "top_k", "questions"}:
        raise ValueError("question set fields are invalid")
    if raw["schema_version"] != "1.0.0":
        raise ValueError("question set schema is unsupported")
    collection = raw["collection_id"]
    top_k = raw["top_k"]
    questions = raw["questions"]
    if not isinstance(collection, str) or not collection:
        raise ValueError("question collection is invalid")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
        raise ValueError("question top_k is invalid")
    if not isinstance(questions, list) or not 10 <= len(questions) <= 15:
        raise ValueError("question count must be between 10 and 15")
    identifiers: set[str] = set()
    validated: list[dict[str, Any]] = []
    for question in questions:
        if not isinstance(question, dict) or set(question) != _QUESTION_FIELDS:
            raise ValueError("question fields are invalid")
        identifier = question["question_id"]
        if (
            not isinstance(identifier, str)
            or not identifier
            or identifier in identifiers
        ):
            raise ValueError("question identities must be unique")
        identifiers.add(identifier)
        if not all(
            isinstance(question[field], str) and question[field]
            for field in ("category", "query", "rationale")
        ):
            raise ValueError("question text is invalid")
        if not isinstance(question["expected_no_evidence"], bool):
            raise ValueError("question no-evidence expectation is invalid")
        for field in (
            "expected_document_ids",
            "expected_chunk_ids",
            "expected_sections",
        ):
            _strings(question[field], field)
        if question["expected_no_evidence"] and any(
            question[field]
            for field in (
                "expected_document_ids",
                "expected_chunk_ids",
                "expected_sections",
            )
        ):
            raise ValueError("no-evidence question cannot expect sources")
        validated.append(question)
    return collection, top_k, validated


def evaluate_questions(raw: dict[str, Any], retriever: Any) -> dict[str, Any]:
    collection, top_k, questions = _validated_questions(raw)
    cases: list[dict[str, Any]] = []
    for question in questions:
        results = tuple(retriever.search(question["query"], limit=top_k))
        documents = {item.document_id for item in results}
        chunks = {item.chunk_id for item in results}
        sections = {item.section_path for item in results if item.section_path}
        collection_ok = all(item.collection_id == collection for item in results)
        no_evidence_ok = (
            not results if question["expected_no_evidence"] else bool(results)
        )
        expected_ok = (
            set(question["expected_document_ids"]) <= documents
            and set(question["expected_chunk_ids"]) <= chunks
            and set(question["expected_sections"]) <= sections
        )
        passed = collection_ok and no_evidence_ok and expected_ok
        cases.append(
            {
                "question_id": question["question_id"],
                "category": question["category"],
                "passed": passed,
                "locators": [
                    f"{item.collection_id}:{item.document_id}:{item.chunk_id}"
                    for item in results
                ],
                "scores": [round(float(item.score), 6) for item in results],
                "sections": [item.section_path for item in results],
            }
        )
    passed_count = sum(case["passed"] for case in cases)
    no_evidence_count = sum(not case["locators"] for case in cases)
    return {
        "schema_version": "1.0.0",
        "collection_id": collection,
        "top_k": top_k,
        "min_score": MIN_SCORE,
        "cases": cases,
        "summary": {
            "questions": len(cases),
            "passed": passed_count,
            "failed": len(cases) - passed_count,
            "answered": len(cases) - no_evidence_count,
            "no_evidence": no_evidence_count,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--index-path", required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        questions = json.loads(args.questions.read_text(encoding="utf-8"))
        collection = questions.get("collection_id")
        if not isinstance(collection, str):
            raise ValueError("question collection is invalid")
        descriptor = EmbeddingDescriptor(
            provider="fastembed",
            model=MODEL,
            version=MODEL_VERSION,
            dimension=DIMENSION,
        )
        spec = KnowledgeIndexSpec(
            collection_id=collection,
            embedding=descriptor,
            distance="cosine",
            chunking_version=CHUNKING_VERSION,
        )
        from app.knowledge.embeddings import FastEmbedEmbeddingAdapter
        from app.knowledge.qdrant_local import QdrantLocalKnowledgeIndex

        embedder = FastEmbedEmbeddingAdapter(
            model=MODEL,
            version=MODEL_VERSION,
            dimension=DIMENSION,
            cache_dir=str((Path.cwd() / ".cache" / "fastembed").resolve()),
        )
        index_path = resolve_knowledge_index_path(
            args.index_path, runtime_root=Path.cwd()
        )
        retriever = QdrantLocalKnowledgeIndex(
            index_path, spec, embedder, min_score=MIN_SCORE
        )
        report = evaluate_questions(questions, retriever)
    except Exception:
        print("[evaluate-showcase-knowledge] error: evaluation failed", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    summary = report["summary"]
    print(
        f"questions={summary['questions']} passed={summary['passed']} "
        f"failed={summary['failed']} no_evidence={summary['no_evidence']}"
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
