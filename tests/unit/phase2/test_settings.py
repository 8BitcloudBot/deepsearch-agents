"""Tests for Phase 2 settings."""

import pytest

from app.settings import Phase2Settings


def test_defaults_are_tutorial_mock():
    s = Phase2Settings.from_env({})
    assert s.app_profile == "tutorial"
    assert s.tutorial_runtime == "mock"
    assert s.web_provider == "mock"
    assert s.catalog_provider == "mock"
    assert s.knowledge_provider == "mock"


def test_rejects_unknown_runtime():
    with pytest.raises(ValueError, match="TUTORIAL_RUNTIME"):
        Phase2Settings.from_env({"TUTORIAL_RUNTIME": "bad"})


def test_rejects_unknown_web_provider():
    with pytest.raises(ValueError, match="WEB_PROVIDER"):
        Phase2Settings.from_env({"WEB_PROVIDER": "unknown"})


def test_rejects_unknown_catalog_provider():
    with pytest.raises(ValueError, match="CATALOG_PROVIDER"):
        Phase2Settings.from_env({"CATALOG_PROVIDER": "unknown"})


def test_rejects_unknown_knowledge_provider():
    with pytest.raises(ValueError, match="KNOWLEDGE_PROVIDER"):
        Phase2Settings.from_env({"KNOWLEDGE_PROVIDER": "unknown"})


def test_allows_deepagents_runtime():
    s = Phase2Settings.from_env({"TUTORIAL_RUNTIME": "deepagents"})
    assert s.tutorial_runtime == "deepagents"


def test_allows_tavily_provider():
    s = Phase2Settings.from_env({"WEB_PROVIDER": "tavily"})
    assert s.web_provider == "tavily"


def test_allows_mysql_provider():
    s = Phase2Settings.from_env({"CATALOG_PROVIDER": "mysql"})
    assert s.catalog_provider == "mysql"


def test_allows_qdrant_local_provider():
    s = Phase2Settings.from_env({"KNOWLEDGE_PROVIDER": "qdrant-local"})
    assert s.knowledge_provider == "qdrant-local"


def test_default_model_name():
    s = Phase2Settings.from_env({})
    assert s.model_name == "openai:gpt-4.1-mini"


def test_custom_model_name():
    s = Phase2Settings.from_env({"MODEL_NAME": "anthropic:claude"})
    assert s.model_name == "anthropic:claude"
