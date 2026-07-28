"""Tests for external adapter normalization with fake SDK clients."""

from unittest.mock import MagicMock, patch

import pytest

from app.providers.ragflow import RAGFlowKnowledgeProvider
from app.providers.tavily import TavilyWebProvider


class TestTavilyNormalization:
    def test_search_results_normalized(self):
        fake_response = {
            "results": [
                {"title": "T1", "url": "https://a.com", "content": "C1"},
                {"title": "T2", "url": "https://b.com", "content": "C2"},
            ]
        }
        with patch("tavily.TavilyClient") as mock_client:
            instance = mock_client.return_value
            instance.search.return_value = fake_response
            provider = TavilyWebProvider(api_key="sk-test")
            result = provider.search("q")
            assert len(result.hits) == 2
            assert result.hits[0].title == "T1"


class TestRAGFlowMapping:
    def test_list_assistants_maps_chats(self):
        fake_chat = MagicMock()
        fake_chat.name = "test-chat"
        fake_chat.description = "desc"
        fake_chat.knowledge_bases = ["kb1"]

        with patch("ragflow_sdk.RAGFlow") as mock_client:
            instance = mock_client.return_value
            instance.list_chats.return_value = [fake_chat]
            provider = RAGFlowKnowledgeProvider(
                api_key="k", base_url="http://x"  # pragma: allowlist secret  # noqa: E501
            )
            assistants = provider.list_assistants()
            assert len(assistants) == 1
            assert assistants[0].name == "test-chat"

    def test_session_cleanup_on_error(self):
        fake_chat = MagicMock()
        fake_chat.name = "test"
        fake_chat.id = "chat-1"
        fake_session = MagicMock()
        fake_session.id = "sess-1"
        fake_session.ask.side_effect = RuntimeError("boom")
        fake_chat.create_session.return_value = fake_session

        with patch("ragflow_sdk.RAGFlow") as mock_client:
            instance = mock_client.return_value
            instance.list_chats.return_value = [fake_chat]
            provider = RAGFlowKnowledgeProvider(
                api_key="k", base_url="http://x"  # pragma: allowlist secret  # noqa: E501
            )
            with pytest.raises(RuntimeError):
                provider.ask("test", "question")
            fake_chat.delete_sessions.assert_called_once_with(["sess-1"])
