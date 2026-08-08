"""RED → GREEN: APP_PROFILE=agent-research settings and app wiring.

Proves tutorial remains the default profile and that the offline
agent-research profile is accepted end-to-end through app.main.
"""

import pytest


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
    monkeypatch.setenv("KNOWLEDGE_PROVIDER", "ragflow")
    for key in ("TAVILY_API_KEY", "RAGFLOW_API_KEY", "RAGFLOW_BASE_URL"):
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
