"""MySQL provider integration tests (require PHASE2_MYSQL_INTEGRATION=1)."""

import os

import mysql.connector
import pytest

pytestmark = pytest.mark.integration

requires_mysql = pytest.mark.skipif(
    not os.environ.get("PHASE2_MYSQL_INTEGRATION"),
    reason="PHASE2_MYSQL_INTEGRATION not set",
)


@requires_mysql
class TestMySQLProvider:
    def test_list_tables(self, mysql_provider):
        tables = mysql_provider.list_tables()
        names = [t.name for t in tables]
        assert "drugs" in names

    def test_describe_table(self, mysql_provider):
        result = mysql_provider.describe_table("drugs")
        assert len(result.columns) >= 1

    def test_preview_table(self, mysql_provider):
        result = mysql_provider.preview_table("drugs")
        assert len(result.rows) >= 1

    def test_execute_select(self, mysql_provider):
        result = mysql_provider.execute_readonly("SELECT COUNT(*) AS cnt FROM drugs")
        assert len(result.rows) == 1

    def test_insert_rejected_by_policy(self, mysql_provider):
        with pytest.raises(Exception):
            mysql_provider.execute_readonly("INSERT INTO drugs VALUES (99,'X',1.0)")

    def test_direct_insert_rejected_by_database(self, mysql_provider):
        conn = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3307")),
            user="tutorial_reader",
            password="tutorial_reader",  # pragma: allowlist secret
            database="research_copilot",
        )
        try:
            cursor = conn.cursor()
            with pytest.raises(mysql.connector.Error):
                cursor.execute("INSERT INTO drugs VALUES (999, 'X', 'test', 1.0)")
                conn.commit()
        finally:
            conn.rollback()
            conn.close()

        conn2 = mysql.connector.connect(
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=int(os.environ.get("MYSQL_PORT", "3307")),
            user="tutorial_reader",
            password="tutorial_reader",  # pragma: allowlist secret
            database="research_copilot",
        )
        try:
            cursor2 = conn2.cursor()
            cursor2.execute("SELECT COUNT(*) FROM drugs")
            row = cursor2.fetchone()
            assert row[0] == 3
        finally:
            conn2.close()


@pytest.fixture
def mysql_provider():
    from app.providers.mysql import MySQLCatalogProvider

    return MySQLCatalogProvider(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3307")),
        user="tutorial_reader",
        password="tutorial_reader",  # pragma: allowlist secret
        database="research_copilot",
    )
