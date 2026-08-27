"""S0 Single Agent strategy: deterministic offline baseline.

S0 reads every source allowed for a case in corpus order, produces a
deterministic Markdown answer and measures topic recall and source
coverage. It never calls a Provider, never touches the network and
always reports ``model_id="mock:deterministic"`` with ``cost_usd=0.0``;
numbers are offline quality proxies and never claim real Provider
quality. Offline latency is never measured or fabricated: ``latency_ms``
is ``None`` so reports render latency as unavailable.

Determinism contract: identical (case, corpus) input yields identical
outputs, so two offline runs fingerprint identically.
"""

import hashlib
import json
import re
from dataclasses import dataclass

from app.evaluation.contracts import EvaluationCase, StrategyOutput
from app.evaluation.source_contracts import Corpus

STRATEGY_ID = "s0-single-agent"
MODEL_ID = "mock:deterministic"
PROMPT_ID = "s0-single-agent-v1"

S0_SYSTEM_PROMPT = (
    "You are S0, a deterministic offline single agent for AI Agent "
    "research evaluation. Read every source allowed for the case in "
    "corpus order, answer the question from that material only, and "
    "report measured topic recall and source coverage. Never claim real "
    "Provider quality: this run is an offline mock baseline."
)

# Deterministic offline configuration; its canonical hash is part of the
# run fingerprint so config changes invalidate old numbers.
S0_CONFIG = {
    "mode": "offline-deterministic",
    "max_source_chars": 4000,
    "topic_match": "case-insensitive-normalized-substring",
}

_MAX_SOURCE_CHARS = S0_CONFIG["max_source_chars"]

# Normalize text for topic matching: lowercase and collapse any run of
# non-alphanumerics to a single space so ``topic-recall`` matches
# ``Topic recall`` deterministically.
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return _sha256(canonical)


def _normalize(text: str) -> str:
    return _NORMALIZE_RE.sub(" ", text.lower()).strip()


@dataclass(frozen=True)
class S0SingleAgentStrategy:
    """S0: deterministic single agent over allowed corpus sources."""

    strategy_id: str = STRATEGY_ID
    model_id: str = MODEL_ID
    prompt_id: str = PROMPT_ID
    prompt_sha256: str = _sha256(S0_SYSTEM_PROMPT)
    config_sha256: str = _canonical_hash(S0_CONFIG)

    def run(self, case: EvaluationCase, corpus: Corpus) -> StrategyOutput:
        allowed = [
            source
            for source in corpus.sources
            if source.source_id in case.allowed_source_ids
        ]
        if not allowed:
            return StrategyOutput(
                case_id=case.case_id,
                status="skipped",
                answer="",
                error_code="no_allowed_sources",
                limitations=("no allowed sources present in the corpus",),
            )

        used_ids: list[str] = []
        excerpts: list[str] = []
        for source in allowed:
            used_ids.append(source.source_id)
            content = source.content
            if len(content) > _MAX_SOURCE_CHARS:
                content = content[:_MAX_SOURCE_CHARS] + "\n\n[TRUNCATED]\n"
            excerpts.append(content)
        combined = "\n".join(excerpts)

        normalized = _normalize(combined)
        matched = [
            topic for topic in case.expected_topics if _normalize(topic) in normalized
        ]
        topic_recall = round(len(matched) / len(case.expected_topics), 4)
        source_coverage = round(len(used_ids) / len(case.allowed_source_ids), 4)
        tool_calls = len(used_ids)

        answer_lines = [
            "# S0 Single Agent Answer",
            "",
            f"**Case:** {case.case_id}",
            f"**Question:** {case.question}",
            "**Execution mode:** offline (deterministic)",
            f"**Model:** {MODEL_ID}",
            f"**Corpus:** {corpus.corpus_id}",
            "",
            "## Sources read",
        ]
        for source in allowed:
            answer_lines.append(f"- {source.source_id} ({source.kind}): {source.title}")
        answer_lines.append("")
        answer_lines.append("## Excerpts")
        for source, excerpt in zip(allowed, excerpts, strict=True):
            answer_lines.append("")
            answer_lines.append(f"### {source.source_id}")
            answer_lines.append(excerpt)
        answer_lines.append("")
        answer_lines.append("## Measured metrics")
        answer_lines.append(
            f"- topic_recall={topic_recall} "
            f"({len(matched)}/{len(case.expected_topics)} "
            f"matched: {', '.join(matched) if matched else 'none'})"
        )
        answer_lines.append(f"- source_coverage={source_coverage}")
        answer_lines.append(f"- tool_calls={tool_calls}")
        answer_lines.append("- cost_usd=0.0 (offline mock)")
        answer = "\n".join(answer_lines) + "\n"

        return StrategyOutput(
            case_id=case.case_id,
            status="success",
            answer=answer,
            # No wall-clock measurement offline: latency stays None so
            # reports render it as unavailable instead of a fabricated ms.
            latency_ms=None,
            cost_usd=0.0,
            tool_calls=tool_calls,
            topic_recall=topic_recall,
            source_coverage=source_coverage,
            limitations=(
                "deterministic offline proxy; not a real Provider quality claim",
            ),
        )
