"""Tests for mock providers and ProviderBundle."""

import pytest

from app.providers.contracts import (
    ProviderBundle,
    SearchResult,
)
from app.providers.mock import (
    MockCatalogProvider,
    MockKnowledgeProvider,
    MockWebProvider,
)


def test_mock_web_returns_fixed_hits():
    provider = MockWebProvider()
    result = provider.search("test query")
    assert isinstance(result, SearchResult)
    assert result.query == "test query"
    assert len(result.hits) >= 2
    assert all(h.title and h.url.startswith("https://") for h in result.hits)


def test_mock_catalog_lists_tables():
    provider = MockCatalogProvider()
    tables = provider.list_tables()
    names = [t.name for t in tables]
    assert "drugs" in names
    assert "inventory" in names


def test_mock_catalog_describe_table():
    provider = MockCatalogProvider()
    result = provider.describe_table("drugs")
    assert len(result.columns) >= 1


def test_mock_catalog_preview_table():
    provider = MockCatalogProvider()
    result = provider.preview_table("drugs")
    assert len(result.rows) >= 1


def test_mock_catalog_rejects_unknown_table():
    provider = MockCatalogProvider()
    with pytest.raises(ValueError):
        provider.describe_table("nonexistent")


def test_mock_knowledge_exposes_tutorial_assistant():
    provider = MockKnowledgeProvider()
    assistants = provider.list_assistants()
    names = [a.name for a in assistants]
    assert any("research" in n for n in names)


def test_mock_knowledge_returns_fixed_answer():
    provider = MockKnowledgeProvider()
    assistants = provider.list_assistants()
    answer = provider.ask(assistants[0].name, "test")
    assert answer.assistant_name == assistants[0].name
    assert len(answer.answer) > 0


def test_provider_bundle_uses_mock_detects_mock():
    bundle = ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="mock",
        catalog_mode="mock",
        knowledge_mode="mock",
    )
    assert bundle.uses_mock is True


def test_provider_bundle_uses_mock_detects_real():
    bundle = ProviderBundle(
        web=MockWebProvider(),
        catalog=MockCatalogProvider(),
        knowledge=MockKnowledgeProvider(),
        web_mode="tavily",
        catalog_mode="mysql",
        knowledge_mode="ragflow",
    )
    assert bundle.uses_mock is False
