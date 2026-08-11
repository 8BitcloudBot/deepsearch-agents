"""Opt-in real Provider smoke gate (P3-6).

By default this module is fully inert: it never touches the network and
never reads credential values into assertions, logs or reports. A real
Provider smoke runs only when BOTH gates pass:

1. ``PHASE3_REAL_PROVIDER_SMOKE`` is set to ``1`` (explicit user opt-in),
2. the Tavily credential is already configured outside this repository.

Each missing gate raises ``pytest.skip`` with an explicit reason, so the
suite reports ``skipped`` — never a pass and never fabricated evidence.
When both gates pass, exactly one harmless bounded smoke call is made: a
single read-only query (``TavilyClient.search`` with ``max_results=1``),
no loops and no retries. A failing
real call fails the test truthfully instead of being converted into
evidence.
"""

import os

import pytest

from app.settings import Phase2Settings

PROVIDER_SMOKE_FLAG = "PHASE3_REAL_PROVIDER_SMOKE"
_PROVIDER_CREDENTIAL_ENVS = ("TAVILY_API_KEY",)


def _opt_in_flag_set() -> bool:
    return os.environ.get(PROVIDER_SMOKE_FLAG) == "1"


def _configured_provider_credentials() -> tuple[str, ...]:
    """Names of configured Provider credentials (never their values).

    Only the configured *presence* of each credential is checked; the
    value is never logged, rendered or asserted.
    """
    return tuple(name for name in _PROVIDER_CREDENTIAL_ENVS if os.environ.get(name))


def test_real_provider_smoke_is_opt_in_and_bounded():
    """One harmless real Provider smoke, strictly opt-in."""
    if not _opt_in_flag_set():
        pytest.skip(
            f"{PROVIDER_SMOKE_FLAG} is not set to '1': real Provider smoke is "
            "opt-in and stays skipped; no credentials were accessed and no "
            "network call was made"
        )
    credentials = _configured_provider_credentials()
    if not credentials:
        pytest.skip(
            f"{PROVIDER_SMOKE_FLAG}=1 but no configured Provider credential was "
            "found (expected TAVILY_API_KEY): skipping "
            "without any network access"
        )
    # Only reachable when the user explicitly opted in AND a Provider
    # credential is already configured outside this repository.
    result = _single_bounded_provider_query(credentials)
    assert result


def _single_bounded_provider_query(credentials: tuple[str, ...]) -> str:
    """Exactly one harmless read-only Provider query (opt-in only)."""
    settings = Phase2Settings.from_env()
    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.search(query="AI agent evaluation", max_results=1)
    return f"tavily search ok ({len(response.get('results', []))} result)"
