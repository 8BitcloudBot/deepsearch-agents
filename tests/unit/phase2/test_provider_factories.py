"""Tests for build_providers factory and provider mode enums."""

import pytest

from app.providers.factory import build_providers
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.settings import Phase2Settings


def test_build_providers_mock_returns_mock_adapters():
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
    settings = Phase2Settings.from_env(
        {
            "WEB_PROVIDER": "tavily",
            "TAVILY_API_KEY": "",
        }
    )
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        build_providers(settings)


def test_build_providers_rejects_ragflow_without_config():
    settings = Phase2Settings.from_env(
        {
            "KNOWLEDGE_PROVIDER": "ragflow",
            "RAGFLOW_API_KEY": "",
            "RAGFLOW_BASE_URL": "",
        }
    )
    with pytest.raises(ValueError, match="RAGFLOW"):
        build_providers(settings)


def test_mysql_requires_tutorial_reader():
    settings = Phase2Settings.from_env(
        {
            "CATALOG_PROVIDER": "mysql",
            "MYSQL_USER": "root",
        }
    )
    with pytest.raises(ValueError, match="tutorial_reader"):
        build_providers(settings)


def test_build_providers_lazy_construction():
    settings = Phase2Settings.from_env(
        {
            "WEB_PROVIDER": "tavily",
            "TAVILY_API_KEY": "sk-fake",  # pragma: allowlist secret
        }
    )
    bundle = build_providers(settings)
    assert bundle.web_mode == "tavily"
    assert not isinstance(bundle.web, MockWebProvider)
