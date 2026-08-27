"""P4-3 semantic support interface: deterministic offline adapter + opt-in real smoke.

``SemanticSupportChecker.check(claim, evidence, context)`` returns a frozen
:class:`SemanticJudgment` with a state in ``supported`` / ``unsupported`` /
``conflict`` / ``unknown`` / ``skipped`` plus ``model_id``, ``prompt_id``,
``prompt_sha256``, ``config_sha256`` and redacted ``reasons``/``limitations``.

Two adapter modes, strictly separated:

* ``mock:deterministic`` (default) -- a pure, offline lexical/semantic proxy
  computed from claim/evidence/context. No I/O, no network, no Provider, no
  randomness: identical inputs produce byte-identical judgments (stable
  fingerprints). ``context`` is accepted and ignored.
* ``real:<model>`` -- runs a real language model, but ONLY when the env var
  ``PHASE4_REAL_SEMANTIC_SMOKE`` equals ``"1"``. Without the flag the checker
  returns ``skipped`` before constructing settings, reading credentials, or
  opening a network connection, and the integration smoke suite pytest-skips
  with an explicit reason.

Fail-closed guarantees:

* ``unknown`` / timeout / malformed model output is NEVER ``supported``.
* A detected conflict is never upgraded to ``supported``.
* Reasons and limitations are redacted (absolute paths, URL credentials,
  secret-like values) before they leave the checker.
* Mock and real results are stamped with their mode and never aggregate
  together: :func:`summarize_semantic` rejects mixed-mode input, and
  ``unknown``/``skipped`` judgments are never counted as support.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.citations.rules import NEGATION_TOKENS, redact, tokenize
from app.citations.settings import Phase4Settings

MOCK_ADAPTER = "mock:deterministic"
REAL_ADAPTER_PREFIX = "real:"
SMOKE_ENV_VAR = "PHASE4_REAL_SEMANTIC_SMOKE"
DEFAULT_PROMPT_ID = "p4-semantic-support-v1"
DEFAULT_SEMANTIC_THRESHOLD = 0.60
MAX_FRAGMENT_LENGTH = 160

# States a real model may emit; "skipped" is reserved for the checker itself.
REAL_STATES = frozenset({"supported", "unsupported", "conflict", "unknown"})

DEFAULT_PROMPT_TEMPLATE = (
    "You judge whether the EVIDENCE quote semantically supports the CLAIM "
    "statement. Reply with JSON only: "
    '{{"state": "supported"|"unsupported"|"conflict"|"unknown", '
    '"reasons": [string, ...], "limitations": [string, ...]}}.\n'
    "CLAIM: {claim}\n"
    "EVIDENCE: {quote}\n"
)


class SemanticState(StrEnum):
    """Stable, deterministic semantic support states (fail-closed)."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"
    SKIPPED = "skipped"


class SemanticMode(StrEnum):
    """Origin of a judgment: mock (offline) or real (model). Never mixed."""

    MOCK = "mock"
    REAL = "real"


def canonical_sha256(payload: Any) -> str:
    """sha256 of the canonical JSON encoding of ``payload`` (deterministic)."""
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text(record: Any, key: str) -> str:
    """String field access that never raises on malformed input."""
    if isinstance(record, Mapping):
        value = record.get(key)
        if isinstance(value, str):
            return value
    return ""


def _fragment(text: str) -> str:
    """Bounded, redacted excerpt of raw text for use inside reasons."""
    truncated = text[:MAX_FRAGMENT_LENGTH]
    if len(text) > MAX_FRAGMENT_LENGTH:
        truncated += "..."
    return redact(truncated)


def render_prompt(
    claim: Any, evidence: Any, template: str = DEFAULT_PROMPT_TEMPLATE
) -> str:
    """Render the semantic prompt for ``claim``/``evidence`` (deterministic)."""
    return template.format(
        claim=_text(claim, "statement"), quote=_text(evidence, "quote")
    )


@dataclass(frozen=True)
class SemanticJudgment:
    """Structured, deterministic outcome of one semantic support check."""

    state: SemanticState
    supported: bool
    mode: SemanticMode
    model_id: str
    prompt_id: str
    prompt_sha256: str
    config_sha256: str
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    fingerprint: str


def _parse_model_output(raw: Any) -> dict[str, Any]:
    """Validate a real model's JSON output; malformed output raises."""
    if not isinstance(raw, Mapping):
        raise ValueError("model output is not a JSON object")
    state = raw.get("state")
    if not isinstance(state, str) or state not in REAL_STATES:
        raise ValueError(f"model output state {state!r} is not a semantic state")

    def _strings(value: Any) -> list[str]:
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError("model output reasons/limitations must be string lists")
        return list(value)

    return {
        "state": state,
        "reasons": _strings(raw.get("reasons", [])),
        "limitations": _strings(raw.get("limitations", [])),
    }


def _default_transport(
    request: Mapping[str, Any],
    *,
    base_url: str | None,
    api_key: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    """Minimal OpenAI-compatible chat completion call (real adapter only).

    Only ever invoked after the opt-in smoke flag has been checked; never used
    in the offline mock path.
    """
    import urllib.request

    endpoint = (base_url or "https://api.openai.com/v1").rstrip(
        "/"
    ) + "/chat/completions"
    body = {
        "model": request.get("model", "openai:gpt-4.1-mini"),
        "messages": [{"role": "user", "content": request.get("prompt", "")}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])


class SemanticSupportChecker:
    """Stateless semantic support checker (P4-3).

    ``check`` never raises and never touches the network or credentials unless
    the real adapter is explicitly opted into via ``PHASE4_REAL_SEMANTIC_SMOKE=1``.
    """

    def __init__(
        self,
        adapter: str = MOCK_ADAPTER,
        *,
        prompt_id: str = DEFAULT_PROMPT_ID,
        prompt_template: str = DEFAULT_PROMPT_TEMPLATE,
        settings: Phase4Settings | None = None,
        transport: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        if not isinstance(adapter, str) or not adapter:
            raise ValueError("adapter must be a non-empty string")
        self.adapter = adapter
        self.prompt_id = prompt_id
        self.prompt_template = prompt_template
        self.settings = settings
        self.transport = transport

    def check(
        self,
        claim: Any,
        evidence: Any,
        context: Mapping[str, Any] | None = None,
    ) -> SemanticJudgment:
        """Judge whether ``evidence`` semantically supports ``claim``."""
        if self.adapter.startswith(REAL_ADAPTER_PREFIX):
            return self._check_real(claim, evidence, context)
        if self.adapter != MOCK_ADAPTER:
            return self._make(
                SemanticState.SKIPPED,
                [
                    f"adapter {self.adapter!r} is not available; only "
                    f"{MOCK_ADAPTER!r} runs offline"
                ],
                ["no adapter was available"],
                claim,
                evidence,
            )
        return self._check_mock(claim, evidence)

    # -- offline deterministic mock adapter --------------------------------

    def _check_mock(self, claim: Any, evidence: Any) -> SemanticJudgment:
        limitations = [
            "offline mock:deterministic adapter: lexical proxy for semantics, "
            "not a language-model judgment"
        ]
        if not isinstance(claim, Mapping) or not isinstance(evidence, Mapping):
            return self._make(
                SemanticState.UNKNOWN,
                ["claim and evidence must be JSON objects (rule s0)"],
                limitations,
                claim,
                evidence,
            )
        statement = _text(claim, "statement")
        quote = _text(evidence, "quote")
        if not statement or not quote:
            return self._make(
                SemanticState.UNKNOWN,
                [
                    "claim statement and evidence quote must be non-empty "
                    "strings (rule s0)"
                ],
                limitations,
                claim,
                evidence,
            )
        claim_tokens = tokenize(statement)
        quote_tokens = set(tokenize(quote))
        if not claim_tokens or not quote_tokens:
            return self._make(
                SemanticState.UNKNOWN,
                ["no tokens available to judge semantic support (rule s0)"],
                limitations,
                claim,
                evidence,
            )
        matched = tuple(sorted(set(claim_tokens) & quote_tokens))
        score = len(matched) / len(claim_tokens)
        negations = sorted((quote_tokens & NEGATION_TOKENS) - set(claim_tokens))

        if score >= DEFAULT_SEMANTIC_THRESHOLD and negations:
            return self._make(
                SemanticState.CONFLICT,
                [
                    "evidence introduces negation term(s) absent from the "
                    "claim: " + ", ".join(negations) + " (rule s3)"
                ],
                limitations,
                claim,
                evidence,
            )
        if score >= DEFAULT_SEMANTIC_THRESHOLD:
            return self._make(
                SemanticState.SUPPORTED,
                [
                    "claim is semantically supported by the evidence quote "
                    f"(rule s1): {_fragment(statement)}"
                ],
                limitations,
                claim,
                evidence,
            )
        return self._make(
            SemanticState.UNSUPPORTED,
            [
                f"claim lacks semantic support: token overlap {score:.2f} is "
                f"below the {DEFAULT_SEMANTIC_THRESHOLD:.2f} confidence "
                "threshold (rule s2)"
            ],
            limitations,
            claim,
            evidence,
        )

    # -- opt-in real adapter ------------------------------------------------

    def _check_real(
        self,
        claim: Any,
        evidence: Any,
        context: Mapping[str, Any] | None,
    ) -> SemanticJudgment:
        # Opt-in gate: without PHASE4_REAL_SEMANTIC_SMOKE=1 we return SKIPPED
        # before constructing settings, reading credentials, or opening any
        # network connection.
        if os.environ.get(SMOKE_ENV_VAR, "") != "1":
            return self._make(
                SemanticState.SKIPPED,
                [
                    "real semantic adapter is opt-in and disabled by default: "
                    "the PHASE4 smoke env flag must equal '1' to run a model; "
                    "no credentials were read and no network request was made"
                ],
                ["no model was consulted"],
                claim,
                evidence,
            )

        settings = (
            self.settings if self.settings is not None else Phase4Settings.from_env()
        )
        prompt = render_prompt(claim, evidence, self.prompt_template)
        model_id = redact(settings.real_semantic_model)
        timeout = settings.real_semantic_timeout_seconds
        if isinstance(context, Mapping) and isinstance(
            context.get("timeout_seconds"), int | float
        ):
            timeout = float(context["timeout_seconds"])
        request = {
            "adapter": self.adapter,
            "model": settings.real_semantic_model,
            "prompt": prompt,
        }
        try:
            transport = (
                self.transport if self.transport is not None else _default_transport
            )
            raw = transport(
                request,
                base_url=settings.real_semantic_base_url,
                api_key=settings.real_semantic_api_key,
                timeout_seconds=timeout,
            )
            parsed = _parse_model_output(raw)
        except TimeoutError:
            return self._make(
                SemanticState.UNKNOWN,
                ["semantic model call timed out; support is undetermined"],
                ["model did not respond within the configured timeout"],
                claim,
                evidence,
                prompt=prompt,
                model_id=model_id,
            )
        except Exception:
            return self._make(
                SemanticState.UNKNOWN,
                [
                    "semantic model call failed or returned malformed output; "
                    "support is undetermined"
                ],
                ["no usable model response was received"],
                claim,
                evidence,
                prompt=prompt,
                model_id=model_id,
            )
        return self._make(
            SemanticState(parsed["state"]),
            parsed["reasons"] + [f"real model judgment via adapter {self.adapter}"],
            parsed["limitations"],
            claim,
            evidence,
            prompt=prompt,
            model_id=model_id,
        )

    # -- shared factory -----------------------------------------------------

    def _make(
        self,
        state: SemanticState,
        reasons: list[str],
        limitations: list[str],
        claim: Any,
        evidence: Any,
        *,
        prompt: str | None = None,
        model_id: str | None = None,
    ) -> SemanticJudgment:
        mode = (
            SemanticMode.REAL
            if self.adapter.startswith(REAL_ADAPTER_PREFIX)
            else SemanticMode.MOCK
        )
        if model_id is None:
            model_id = MOCK_ADAPTER if mode is SemanticMode.MOCK else redact("unknown")
        rendered = (
            prompt
            if prompt is not None
            else render_prompt(claim, evidence, self.prompt_template)
        )
        prompt_sha256 = canonical_sha256(rendered)
        config_sha256 = canonical_sha256(
            {
                "adapter": self.adapter,
                "prompt_id": self.prompt_id,
                "model_id": model_id,
                "threshold": DEFAULT_SEMANTIC_THRESHOLD,
                "smoke_env": SMOKE_ENV_VAR,
            }
        )
        redacted_reasons = tuple(redact(reason) for reason in reasons)
        redacted_limitations = tuple(redact(limitation) for limitation in limitations)
        payload = {
            "state": state.value,
            "mode": mode.value,
            "model_id": model_id,
            "prompt_id": self.prompt_id,
            "prompt_sha256": prompt_sha256,
            "config_sha256": config_sha256,
            "reasons": list(redacted_reasons),
            "limitations": list(redacted_limitations),
            "claim_id": _text(claim, "claim_id") or "?",
            "evidence_id": _text(evidence, "evidence_id") or "?",
        }
        return SemanticJudgment(
            state=state,
            supported=state is SemanticState.SUPPORTED,
            mode=mode,
            model_id=model_id,
            prompt_id=self.prompt_id,
            prompt_sha256=prompt_sha256,
            config_sha256=config_sha256,
            reasons=redacted_reasons,
            limitations=redacted_limitations,
            fingerprint=canonical_sha256(payload),
        )


def summarize_semantic(judgments: tuple[SemanticJudgment, ...]) -> dict[str, Any]:
    """Summarize judgments, refusing to aggregate mock and real together.

    ``unknown`` and ``skipped`` are never counted as support; only judgments
    whose ``state`` is ``supported`` contribute to ``supported``.
    """
    modes = {j.mode for j in judgments}
    if len(modes) > 1:
        raise ValueError(
            "cannot aggregate mock and real semantic judgments together "
            "(mock/real results must never be combined)"
        )
    counts = {state: 0 for state in SemanticState}
    for judgment in judgments:
        counts[judgment.state] += 1
    return {
        "mode": next(iter(modes)) if modes else None,
        "count": len(judgments),
        "states": {state.value: counts[state] for state in SemanticState},
        "supported": sum(1 for j in judgments if j.supported),
        "unknown_or_skipped": counts[SemanticState.UNKNOWN]
        + counts[SemanticState.SKIPPED],
    }


__all__ = [
    "DEFAULT_PROMPT_ID",
    "DEFAULT_PROMPT_TEMPLATE",
    "DEFAULT_SEMANTIC_THRESHOLD",
    "MAX_FRAGMENT_LENGTH",
    "MOCK_ADAPTER",
    "REAL_ADAPTER_PREFIX",
    "REAL_STATES",
    "SMOKE_ENV_VAR",
    "SemanticJudgment",
    "SemanticMode",
    "SemanticState",
    "SemanticSupportChecker",
    "canonical_sha256",
    "render_prompt",
    "summarize_semantic",
]
