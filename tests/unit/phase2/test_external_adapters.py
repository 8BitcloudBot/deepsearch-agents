"""Tests for external adapter normalization with fake SDK clients."""

from unittest.mock import MagicMock, patch

import pytest

from app.providers.mysql import MySQLCatalogProvider
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

    def test_connection_uses_pure_python_connector(self):
        with patch("mysql.connector.connect") as mock_connect:
            conn = MagicMock()
            conn.cursor.return_value.fetchall.return_value = []
            mock_connect.return_value = conn
            self._provider().list_tables()

        assert mock_connect.call_args.kwargs["use_pure"] is True

    def test_cursor_stays_open_until_rows_are_consumed(self):
        class StrictCursor:
            def __init__(self):
                self.closed = False

            def execute(self, sql):
                assert sql == "SHOW TABLES"

            def fetchall(self):
                if self.closed:
                    raise RuntimeError("cursor read after close")
                return [("drugs",)]

            def close(self):
                self.closed = True

        with patch("mysql.connector.connect") as mock_connect:
            cursor = StrictCursor()
            conn = MagicMock()
            conn.cursor.return_value = cursor
            mock_connect.return_value = conn
            tables = self._provider().list_tables()

        assert [table.name for table in tables] == ["drugs"]
        assert cursor.closed is True
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
