"""Tests for external adapter normalization with fake SDK clients."""

from unittest.mock import MagicMock, patch

import pytest

from app.providers.mysql import MySQLCatalogProvider
from app.providers.ragflow import RAGFlowKnowledgeProvider
from app.providers.tavily import TavilyWebProvider

FAKE_KEY = "sk-b6-secret-12345"  # pragma: allowlist secret
RAW_MARKER = "raw-b6-payload-marker"
PATH_MARKER = "/var/b6-cache/raw-response.json"


def _sensitive_error() -> RuntimeError:
    return RuntimeError(
        f"access denied key={FAKE_KEY} payload={RAW_MARKER} path={PATH_MARKER}"
    )


def _assert_clean(text: str) -> None:
    for marker in (FAKE_KEY, RAW_MARKER, PATH_MARKER):
        assert marker not in text, f"sensitive marker leaked into {text!r}"


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
            provider = TavilyWebProvider(
                api_key="sk-test"
            )  # pragma: allowlist secret  # noqa: E501
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
                api_key="k",  # pragma: allowlist secret  # noqa: E501
                base_url="http://x",  # pragma: allowlist secret  # noqa: E501
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
                api_key="k",  # pragma: allowlist secret  # noqa: E501
                base_url="http://x",  # pragma: allowlist secret  # noqa: E501
            )
            with pytest.raises(RuntimeError):
                provider.ask("test", "question")
            fake_chat.delete_sessions.assert_called_once_with(["sess-1"])


class TestTavilyFailureRedaction:
    def test_search_failure_redacted(self):
        with patch("tavily.TavilyClient") as mock_client:
            instance = mock_client.return_value
            instance.search.side_effect = _sensitive_error()
            provider = TavilyWebProvider(api_key=FAKE_KEY)
            with pytest.raises(RuntimeError) as excinfo:
                provider.search("q")
        _assert_clean(str(excinfo.value))
        assert "Tavily" in str(excinfo.value)


class TestRAGFlowFailureRedaction:
    def test_list_assistants_failure_redacted(self):
        with patch("ragflow_sdk.RAGFlow") as mock_client:
            instance = mock_client.return_value
            instance.list_chats.side_effect = _sensitive_error()
            provider = RAGFlowKnowledgeProvider(api_key=FAKE_KEY, base_url="http://x")
            with pytest.raises(RuntimeError) as excinfo:
                provider.list_assistants()
        _assert_clean(str(excinfo.value))
        assert "RAGFlow" in str(excinfo.value)

    def test_ask_failure_redacted_and_session_cleaned(self):
        fake_chat = MagicMock()
        fake_chat.name = "test"
        fake_chat.id = "chat-1"
        fake_session = MagicMock()
        fake_session.id = "sess-1"
        fake_session.ask.side_effect = _sensitive_error()
        fake_chat.create_session.return_value = fake_session

        with patch("ragflow_sdk.RAGFlow") as mock_client:
            instance = mock_client.return_value
            instance.list_chats.return_value = [fake_chat]
            provider = RAGFlowKnowledgeProvider(api_key=FAKE_KEY, base_url="http://x")
            with pytest.raises(RuntimeError) as excinfo:
                provider.ask("test", "question")
        _assert_clean(str(excinfo.value))
        fake_chat.delete_sessions.assert_called_once_with(["sess-1"])


class TestRAGFlowCleanup:
    def test_session_cleanup_on_success(self):
        fake_chat = MagicMock()
        fake_chat.name = "test"
        fake_chat.id = "chat-1"
        fake_session = MagicMock()
        fake_session.id = "sess-1"
        fake_msg = MagicMock()
        fake_msg.content = "clean answer"
        fake_session.ask.return_value = [fake_msg]
        fake_chat.create_session.return_value = fake_session

        with patch("ragflow_sdk.RAGFlow") as mock_client:
            instance = mock_client.return_value
            instance.list_chats.return_value = [fake_chat]
            provider = RAGFlowKnowledgeProvider(
                api_key="k",  # pragma: allowlist secret
                base_url="http://x",
            )
            answer = provider.ask("test", "question")
        assert answer.answer == "clean answer"
        fake_chat.delete_sessions.assert_called_once_with(["sess-1"])


class TestMySQLCleanupAndRedaction:
    def _provider(self) -> MySQLCatalogProvider:
        return MySQLCatalogProvider(
            host="db.local",
            port=3306,
            user="tutorial_reader",
            password=FAKE_KEY,
            database="drugs",
        )

    def test_connection_closed_on_success(self):
        with patch("mysql.connector.connect") as mock_connect:
            conn = MagicMock()
            conn.cursor.return_value.fetchall.return_value = [("drugs",)]
            mock_connect.return_value = conn
            tables = self._provider().list_tables()
        assert [t.name for t in tables] == ["drugs"]
        conn.close.assert_called_once()

    def test_query_failure_redacted_and_connection_closed(self):
        with patch("mysql.connector.connect") as mock_connect:
            conn = MagicMock()
            conn.cursor.return_value.execute.side_effect = _sensitive_error()
            mock_connect.return_value = conn
            with pytest.raises(RuntimeError) as excinfo:
                self._provider().list_tables()
            conn.close.assert_called_once()
        _assert_clean(str(excinfo.value))
        assert "MySQL" in str(excinfo.value)

    def test_connect_failure_redacted(self):
        with patch("mysql.connector.connect", side_effect=_sensitive_error()):
            with pytest.raises(RuntimeError) as excinfo:
                self._provider().list_tables()
        _assert_clean(str(excinfo.value))
