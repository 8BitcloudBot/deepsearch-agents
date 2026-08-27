import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.evaluate_showcase_knowledge import evaluate_questions

QUESTIONS_PATH = Path("data/knowledge/showcase-v1/questions.json")


class FakeRetriever:
    def __init__(self, results):
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int):
        self.calls.append((query, limit))
        return self.results.get(query, ())


def chunk(document_id: str, chunk_id: str, section: str, score: float = 0.8):
    return SimpleNamespace(
        collection_id="deepsearch-showcase-v1",
        document_id=document_id,
        chunk_id=chunk_id,
        section_path=section,
        score=score,
    )


def question_set(question: dict, *, top_k: int) -> dict:
    padding = [
        {
            "question_id": f"padding-{index:02d}",
            "category": "no-evidence",
            "query": f"missing-{index:02d}",
            "expected_document_ids": [],
            "expected_chunk_ids": [],
            "expected_sections": [],
            "expected_no_evidence": True,
            "rationale": "Schema-sized unit fixture.",
        }
        for index in range(1, 10)
    ]
    return {
        "schema_version": "1.0.0",
        "collection_id": "deepsearch-showcase-v1",
        "top_k": top_k,
        "questions": [question, *padding],
    }


def test_evaluate_questions_requires_expected_documents_chunks_and_sections() -> None:
    questions = question_set(
        {
            "question_id": "q01",
            "category": "comparison",
            "query": "compare",
            "expected_document_ids": ["doc-a", "doc-b"],
            "expected_chunk_ids": ["doc-a-0001", "doc-b-0002"],
            "expected_sections": ["A > One", "B > Two"],
            "expected_no_evidence": False,
            "rationale": "Both sources are required.",
        },
        top_k=5,
    )
    retriever = FakeRetriever(
        {
            "compare": (
                chunk("doc-a", "doc-a-0001", "A > One"),
                chunk("doc-b", "doc-b-0002", "B > Two", 0.7),
            )
        }
    )

    report = evaluate_questions(questions, retriever)

    assert report["summary"] == {
        "questions": 10,
        "passed": 10,
        "failed": 0,
        "answered": 1,
        "no_evidence": 9,
    }
    assert report["cases"][0]["passed"] is True
    assert report["cases"][0]["locators"] == [
        "deepsearch-showcase-v1:doc-a:doc-a-0001",
        "deepsearch-showcase-v1:doc-b:doc-b-0002",
    ]
    assert retriever.calls[0] == ("compare", 5)


def test_evaluate_questions_requires_empty_result_for_no_evidence() -> None:
    questions = question_set(
        {
            "question_id": "q12",
            "category": "no-evidence",
            "query": "unknown",
            "expected_document_ids": [],
            "expected_chunk_ids": [],
            "expected_sections": [],
            "expected_no_evidence": True,
            "rationale": "The corpus has no answer.",
        },
        top_k=3,
    )

    report = evaluate_questions(questions, FakeRetriever({"unknown": ()}))

    assert report["cases"][0]["passed"] is True
    assert report["cases"][0]["locators"] == []
    assert report["summary"]["no_evidence"] == 10


def test_evaluate_questions_rejects_wrong_collection_and_duplicate_ids() -> None:
    questions = question_set(
        {
            "question_id": "q01",
            "category": "fact",
            "query": "q",
            "expected_document_ids": ["doc"],
            "expected_chunk_ids": ["doc-0001"],
            "expected_sections": ["Doc"],
            "expected_no_evidence": False,
            "rationale": "Fact.",
        },
        top_k=3,
    )
    wrong = chunk("doc", "doc-0001", "Doc")
    wrong.collection_id = "another-collection"

    report = evaluate_questions(questions, FakeRetriever({"q": (wrong,)}))
    assert report["cases"][0]["passed"] is False

    questions["questions"][1] = dict(questions["questions"][0])
    with pytest.raises(ValueError, match="question"):
        evaluate_questions(questions, FakeRetriever({}))


def test_public_questions_do_not_contain_direct_commands() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    direct_command_tokens = (
        ("ignore", "all", "previous", "instructions"),
        ("reveal", "the", "system", "prompt"),
    )

    for question in questions:
        query = question["query"].casefold()
        for command in direct_command_tokens:
            assert " ".join(command) not in query, question["question_id"]
