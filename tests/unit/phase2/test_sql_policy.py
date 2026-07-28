"""Tests for read-only SQL policy."""

import pytest

from app.providers.mysql import ReadOnlyQueryError, validate_readonly_query

VALID = [
    "SELECT * FROM drugs",
    "SELECT name, price FROM drugs WHERE category='NSAID'",
    "WITH cte AS (SELECT * FROM drugs) SELECT * FROM cte",
]

INVALID = [
    ("INSERT INTO drugs VALUES (4,'X',2.0)", "INSERT"),
    ("DELETE FROM drugs", "DELETE"),
    ("UPDATE drugs SET price=0", "UPDATE"),
    ("CREATE TABLE x (id INT)", "CREATE"),
    ("DROP TABLE drugs", "DROP"),
    ("ALTER TABLE drugs ADD COLUMN x INT", "ALTER"),
    ("SELECT * FROM other_db.drugs", "cross-database"),
    ("SELECT * FROM drugs; SELECT * FROM inventory", "multi-statement"),
]


@pytest.mark.parametrize("query", VALID)
def test_readonly_policy_accepts_valid_sql(query):
    validate_readonly_query(query, database="research_copilot")


@pytest.mark.parametrize("query,reason", INVALID)
def test_readonly_policy_rejects_unsafe_sql(query, reason):
    with pytest.raises(ReadOnlyQueryError):
        validate_readonly_query(query, database="research_copilot")
