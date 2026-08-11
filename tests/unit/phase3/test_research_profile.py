"""RED → GREEN: APP_PROFILE=agent-research settings and app wiring.

Proves tutorial remains the default profile and that the offline
agent-research profile is accepted end-to-end through app.main, and
that the P4.5-1 showcase profile is inert (never constructs providers)
regardless of its dedicated opt-in state.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_default_app_profile_is_tutorial():
    from app.settings import Phase2Settings

    s = Phase2Settings.from_env({})
    assert s.app_profile == "tutorial"


def test_agent_research_profile_accepted():
    from app.settings import Phase2Settings

    s = Phase2Settings.from_env({"APP_PROFILE": "agent-research"})
    assert s.app_profile == "agent-research"


def test_agent_research_profile_keeps_mock_defaults():
    from app.settings import Phase2Settings

    s = Phase2Settings.from_env({"APP_PROFILE": "agent-research"})
    assert s.tutorial_runtime == "mock"
    assert s.web_provider == "mock"
    assert s.catalog_provider == "mock"
    assert s.knowledge_provider == "mock"


def test_rejects_unknown_app_profile():
    from app.settings import Phase2Settings

    with pytest.raises(ValueError, match="APP_PROFILE"):
        Phase2Settings.from_env({"APP_PROFILE": "unknown"})


def test_agent_research_runtime_is_importable():
    from app.research.runtime import AgentResearchRuntime

    assert callable(AgentResearchRuntime)


def test_agent_research_corpus_is_importable():
    from app.research.corpus import load_corpus

    assert callable(load_corpus)


def test_agent_research_skips_build_providers_with_residual_env(monkeypatch):
    """agent-research must start even when Phase 2 real-provider env vars
    are present as residuals without credentials, and must never call
    build_providers."""
    monkeypatch.setenv("APP_PROFILE", "agent-research")
    monkeypatch.setenv("WEB_PROVIDER", "tavily")
    monkeypatch.setenv("CATALOG_PROVIDER", "mysql")
    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "qdrant-local")
    for key in ("TAVILY_API_KEY",):
        monkeypatch.delenv(key, raising=False)

    calls: list = []

    def spy(settings):
        calls.append(settings)
        raise AssertionError("build_providers must not run for agent-research")

    monkeypatch.setattr("app.main.build_providers", spy)
    from app.main import create_app

    app = create_app()
    assert calls == []
    assert app.title == "research-copilot-api"


def test_tutorial_profile_still_builds_providers(monkeypatch):
    """Tutorial keeps eager provider construction unchanged."""
    monkeypatch.delenv("APP_PROFILE", raising=False)
    calls: list = []

    def spy(settings):
        calls.append(settings)
        return None

    monkeypatch.setattr("app.main.build_providers", spy)
    from app.main import create_app

    create_app()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_health_default_reports_tutorial_profile(monkeypatch):
    monkeypatch.delenv("APP_PROFILE", raising=False)
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/health")).json()

    assert data["status"] == "ok"
    assert data["phase"] == "2"
    assert data["tutorial_profile"] == "tutorial"
    assert data["app_profile"] == "tutorial"


@pytest.mark.asyncio
async def test_health_reports_agent_research_profile(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "agent-research")
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/health")).json()

    # Health changes are additive: existing Phase 2 keys are preserved.
    assert data["status"] == "ok"
    assert data["phase"] == "2"
    assert data["tutorial_profile"] == "tutorial"
    assert data["tutorial_runtime"] == "mock"
    assert data["app_profile"] == "agent-research"


# ── P4.5-1 showcase profile wiring ─────────────────────────────────────────


def test_showcase_profile_accepted():
    from app.settings import Phase2Settings

    s = Phase2Settings.from_env({"APP_PROFILE": "showcase"})
    assert s.app_profile == "showcase"


def test_showcase_profile_keeps_mock_defaults():
    from app.settings import Phase2Settings

    s = Phase2Settings.from_env({"APP_PROFILE": "showcase"})
    assert s.tutorial_runtime == "mock"
    assert s.web_provider == "mock"
    assert s.catalog_provider == "mock"
    assert s.knowledge_provider == "mock"


def test_showcase_profile_never_builds_providers_with_opt_in(monkeypatch):
    """Showcase is inert in P4.5-1: even with its opt-in exactly enabled
    and every source declared, it must never construct providers."""
    monkeypatch.setenv("APP_PROFILE", "showcase")
    monkeypatch.setenv("SHOWCASE_ENABLED", "1")
    monkeypatch.setenv("SHOWCASE_SOURCES", "web,mysql,knowledge,uploaded-file")

    calls: list = []

    def spy(settings):
        calls.append(settings)
        raise AssertionError("build_providers must not run for showcase")

    monkeypatch.setattr("app.main.build_providers", spy)
    from app.main import create_app

    app = create_app()
    assert calls == []
    assert app.title == "research-copilot-api"


def test_showcase_profile_inert_without_opt_in(monkeypatch):
    """Showcase without its dedicated opt-in stays inert and still starts
    deterministically."""
    monkeypatch.setenv("APP_PROFILE", "showcase")
    monkeypatch.delenv("SHOWCASE_ENABLED", raising=False)
    monkeypatch.delenv("SHOWCASE_SOURCES", raising=False)

    calls: list = []

    def spy(settings):
        calls.append(settings)
        raise AssertionError("build_providers must not run for showcase")

    monkeypatch.setattr("app.main.build_providers", spy)
    from app.main import create_app

    app = create_app()
    assert calls == []
    assert app.title == "research-copilot-api"


def test_showcase_profile_starts_with_residual_provider_env(monkeypatch):
    """Showcase never reads Phase 2 real-provider credentials; residual
    env vars without credentials must not break startup."""
    monkeypatch.setenv("APP_PROFILE", "showcase")
    monkeypatch.setenv("WEB_PROVIDER", "tavily")
    monkeypatch.setenv("CATALOG_PROVIDER", "mysql")
    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "qdrant-local")
    for key in ("TAVILY_API_KEY",):
        monkeypatch.delenv(key, raising=False)

    from app.main import create_app

    app = create_app()
    assert app.title == "research-copilot-api"


@pytest.mark.asyncio
async def test_health_reports_showcase_profile(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "showcase")
    monkeypatch.setenv("SHOWCASE_ENABLED", "1")
    from httpx import ASGITransport, AsyncClient

    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data = (await client.get("/health")).json()

    assert data["status"] == "ok"
    assert data["phase"] == "2"
    assert data["app_profile"] == "showcase"
