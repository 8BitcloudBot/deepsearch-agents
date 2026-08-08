"""P4-3 opt-in real-model semantic smoke.

Skipped with an explicit reason unless ``PHASE4_REAL_SEMANTIC_SMOKE=1``.
Without the flag this module never reads credentials and never touches the
network: the checker itself also refuses to run the real adapter (returns
``skipped``), so both layers are fail-closed by default.
"""

import os
import re

import pytest

from app.citations.fixtures import SEED_CLAIMS, SEED_EVIDENCE
from app.citations.semantic import (
    SMOKE_ENV_VAR,
    SemanticState,
    SemanticSupportChecker,
)
from app.settings import Phase4Settings

pytestmark = pytest.mark.skipif(
    os.environ.get(SMOKE_ENV_VAR, "") != "1",
    reason=(
        f"{SMOKE_ENV_VAR} is not set to '1'; the real semantic smoke is "
        "opt-in and stays offline otherwise"
    ),
)

HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_REAL_STATES = (
    SemanticState.SUPPORTED,
    SemanticState.UNSUPPORTED,
    SemanticState.CONFLICT,
    SemanticState.UNKNOWN,
)


def test_real_semantic_smoke_runs_when_opted_in():
    settings = Phase4Settings.from_env()
    assert settings.real_semantic_smoke is True
    checker = SemanticSupportChecker(adapter=f"real:{settings.real_semantic_model}")

    for claim, evidence in zip(SEED_CLAIMS, SEED_EVIDENCE):
        j = checker.check(claim, evidence, {})
        assert j.state in ALLOWED_REAL_STATES
        assert j.supported == (j.state is SemanticState.SUPPORTED)
        if j.state in (SemanticState.UNKNOWN, SemanticState.SKIPPED):
            assert j.supported is False
        assert HEX64.match(j.prompt_sha256)
        assert HEX64.match(j.config_sha256)
        assert HEX64.match(j.fingerprint)
        blob = "\n".join(j.reasons + j.limitations)
        if settings.real_semantic_api_key:
            assert settings.real_semantic_api_key not in blob
