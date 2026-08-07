"""Tests for build_providers factory and provider mode enums."""

import pytest

from app.providers.factory import build_providers
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)
from app.providers.mysql import MySQLCatalogProvider
from app.settings import Phase2Settings

FAKE_KEY = "sk-b6-secret-12345"  # pragma: allowlist secret
PATH_MARKER = "/var/b6-cache/raw-response.json"


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


def test_factory_errors_never_echo_credentials_or_paths():
    env_cases = [
        {"WEB_PROVIDER": "tavily", "TAVILY_API_KEY": ""},
        {
            "KNOWLEDGE_PROVIDER": "ragflow",
            "RAGFLOW_API_KEY": "",
            "RAGFLOW_BASE_URL": "",
        },
        {"CATALOG_PROVIDER": "mysql", "MYSQL_USER": "root"},
    ]
    for env in env_cases:
        settings = Phase2Settings.from_env(env)
        with pytest.raises(ValueError) as excinfo:
            build_providers(settings)
        text = str(excinfo.value)
        assert FAKE_KEY not in text, f"credential leaked: {text!r}"
        assert PATH_MARKER not in text, f"absolute path leaked: {text!r}"


def test_bundle_repr_never_exposes_credentials():
    settings = Phase2Settings.from_env(
        {
            "CATALOG_PROVIDER": "mysql",
            "MYSQL_USER": "tutorial_reader",
            "MYSQL_PASSWORD": FAKE_KEY,
        }
    )
    bundle = build_providers(settings)
    assert isinstance(bundle.catalog, MySQLCatalogProvider)
    assert FAKE_KEY not in repr(bundle)
    assert FAKE_KEY not in repr(bundle.catalog)
