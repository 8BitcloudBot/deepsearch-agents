"""Phase 2-2 remediation RED tests."""

import pytest


class TestProviderEnumValidation:
    def test_app_profile_only_tutorial(self):
        from app.settings import Phase2Settings

        with pytest.raises(ValueError):
            Phase2Settings.from_env({"APP_PROFILE": "agent-research"})


class TestExecuteReadonlyLimits:
    def test_provider_execute_readonly_clamps_limit_999(self):
        """Provider must clamp limit=999 to 100 in generated SQL."""
        from unittest.mock import MagicMock

        from app.providers.mysql import MySQLCatalogProvider

        # Create provider with mocked connection
        provider = MySQLCatalogProvider(
            host="h",
            port=1,
            user="u",
            password="p",  # pragma: allowlist secret
            database="d",  # pragma: allowlist secret
        )
        fake_cursor = MagicMock()
        fake_cursor.description = [("col",)]
        fake_cursor.fetchall.return_value = [(1,)]
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        provider._connect = lambda: fake_conn
        provider.execute_readonly("SELECT * FROM drugs", limit=999)
        sql = fake_cursor.execute.call_args[0][0]
        assert "LIMIT 100" in sql, f"Expected LIMIT 100 in SQL, got: {sql}"

    def test_provider_execute_readonly_clamps_limit_0_to_1(self):
        """Provider must clamp limit=0 to 1."""
        from unittest.mock import MagicMock

        from app.providers.mysql import MySQLCatalogProvider

        provider = MySQLCatalogProvider(
            host="h",
            port=1,
            user="u",
            password="p",  # pragma: allowlist secret
            database="d",  # pragma: allowlist secret
        )
        fake_cursor = MagicMock()
        fake_cursor.description = [("col",)]
        fake_cursor.fetchall.return_value = [(1,)]
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = fake_cursor

        provider._connect = lambda: fake_conn
        provider.execute_readonly("SELECT * FROM drugs", limit=0)
        sql = fake_cursor.execute.call_args[0][0]
        assert "LIMIT 1" in sql, f"Expected LIMIT 1 in SQL, got: {sql}"

    def test_semicolon_trailing_rejected(self):
        from app.providers.mysql import ReadOnlyQueryError, validate_readonly_query

        with pytest.raises(ReadOnlyQueryError):
            validate_readonly_query("SELECT * FROM drugs;", database="research_copilot")
