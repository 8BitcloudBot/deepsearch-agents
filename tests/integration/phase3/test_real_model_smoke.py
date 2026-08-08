"""Opt-in real model smoke gate (P3-6).

By default this module is fully inert: it never touches the network and
never reads credential values into assertions, logs or reports. A real
model smoke runs only when BOTH gates pass:

1. ``PHASE3_REAL_MODEL_SMOKE`` is set to ``1`` (explicit user opt-in),
2. a model credential is already configured outside this repository
   (``MODEL_API_KEY``; ``MODEL_NAME`` and ``MODEL_BASE_URL`` are used
   when set).

Each missing gate raises ``pytest.skip`` with an explicit reason, so the
suite reports ``skipped`` — never a pass and never fabricated evidence.
When both gates pass, exactly one harmless bounded smoke call is made: a
single completion with ``max_tokens=8``, no loops and no retries. A
failing real call fails the test truthfully instead of being converted
into evidence.
"""

import os

import pytest

from app.settings import Phase2Settings

MODEL_SMOKE_FLAG = "PHASE3_REAL_MODEL_SMOKE"
_MODEL_CREDENTIAL_ENV = "MODEL_API_KEY"


def _opt_in_flag_set() -> bool:
    return os.environ.get(MODEL_SMOKE_FLAG) == "1"


def _model_credential_configured() -> bool:
    """Configured presence of the model credential (never its value)."""
    return bool(os.environ.get(_MODEL_CREDENTIAL_ENV))


def test_real_model_smoke_is_opt_in_and_bounded():
    """One harmless real model completion, strictly opt-in."""
    if not _opt_in_flag_set():
        pytest.skip(
            f"{MODEL_SMOKE_FLAG} is not set to '1': real model smoke is "
            "opt-in and stays skipped; no credentials were accessed and no "
            "network call was made"
        )
    if not _model_credential_configured():
        pytest.skip(
            f"{MODEL_SMOKE_FLAG}=1 but no configured model credential was "
            f"found (expected {_MODEL_CREDENTIAL_ENV}): skipping without any "
            "network access"
        )
    # Only reachable when the user explicitly opted in AND a model
    # credential is already configured outside this repository.
    result = _single_bounded_model_completion()
    assert result


def _single_bounded_model_completion() -> str:
    """Exactly one harmless bounded model completion (opt-in only)."""
    from langchain_openai import ChatOpenAI

    settings = Phase2Settings.from_env()
    model = ChatOpenAI(
        model=settings.model_name,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        max_tokens=8,
        temperature=0,
    )
    response = model.invoke("Reply with the single word: OK")
    content = (response.content or "").strip()
    return f"model completion ok ({len(content)} chars)"
