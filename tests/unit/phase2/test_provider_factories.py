"""Tests for build_providers factory and provider mode enums."""

import pytest

from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.settings import Phase2Settings


def test_build_providers_mock_returns_mock_adapters():
    """build_providers with mock settings must return mock adapters."""
    from app.providers.factory import build_providers

    settings = Phase2Settings.from_env(
        {
            "WEB_PROVIDER": "mock",
            "CATALOG_PROVIDER": "mock",
            "KNOWLEDGE_PROVIDER": "mock",
        }
    )
    bundle = build_providers(settings)
    assert isinstance(bundle.web, MockWebProvider)
    assert isinstance(bundle.catalog, MockCatalogProvider)
    assert isinstance(bundle.knowledge, MockKnowledgeProvider)
    assert bundle.web_mode == "mock"
    assert bundle.catalog_mode == "mock"
    assert bundle.knowledge_mode == "mock"


def test_build_providers_rejects_tavily_without_key():
    """build_providers with tavily but no API key must raise."""
    from app.providers.factory import build_providers

    settings = Phase2Settings.from_env(
        {
            "WEB_PROVIDER": "tavily",
            "TAVILY_API_KEY": "",
        }
    )
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        build_providers(settings)


def test_build_providers_rejects_ragflow_without_config():
    """build_providers with ragflow but missing base_url/key must raise."""
    from app.providers.factory import build_providers

    settings = Phase2Settings.from_env(
        {
            "KNOWLEDGE_PROVIDER": "ragflow",
            "RAGFLOW_API_KEY": "",
            "RAGFLOW_BASE_URL": "",
        }
    )
    with pytest.raises(ValueError, match="RAGFLOW"):
        build_providers(settings)


def test_build_providers_lazy_construction():
    """Real adapters must be lazy — no network during build."""
    from app.providers.factory import build_providers

    # Even with valid-looking settings (but no real keys),
    # the factory should not try to connect
    settings = Phase2Settings.from_env(
        {
            "WEB_PROVIDER": "tavily",
            "TAVILY_API_KEY": "sk-fake",  # pragma: allowlist secret,
        }
    )
    # The factory creates the adapter but adapter is lazy — no connection yet
    bundle = build_providers(settings)
    assert bundle.web_mode == "tavily"
    # Provider should be a TavilyWebProvider, not MockWebProvider
    assert not isinstance(bundle.web, MockWebProvider)
