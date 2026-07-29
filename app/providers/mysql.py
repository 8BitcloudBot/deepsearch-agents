"""Controlled read-only MySQL adapter."""

import re

import sqlglot
from sqlglot.errors import ParseError

from app.providers.contracts import QueryResult, TableInfo

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_table_name(name: str) -> None:
    if not _TABLE_NAME_RE.match(name):
        raise ReadOnlyQueryError(f"Invalid table name: {name!r}")


class ReadOnlyQueryError(ValueError):
    pass


def validate_readonly_query(query: str, *, database: str) -> None:
    """Validate that query is a single read-only SELECT on the given database."""
    # Reject multi-statement and trailing semicolons
    stripped = query.strip()
    if ";" in stripped[:-1] if len(stripped) > 1 else ";" in stripped:
        raise ReadOnlyQueryError("Multiple statements not allowed")
    if stripped.endswith(";"):
        raise ReadOnlyQueryError("Trailing semicolons not allowed")

    # Reject comments
    if "--" in query or "/*" in query:
        raise ReadOnlyQueryError("Comments not allowed in query")

    try:
        parsed = sqlglot.parse_one(query, dialect="mysql")
    except ParseError as exc:
        raise ReadOnlyQueryError(f"SQL parse error: {exc}") from exc

    # Walk entire AST to reject DDL/DML/commands/file/lock/cross-db access
    for node in parsed.walk():
        kind = node.key.upper() if hasattr(node, "key") else ""
        if kind in (
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "CALL",
            "LOAD_FILE",
            "INTO OUTFILE",
            "LOCK",
            "UNLOCK",
            "TRUNCATE",
            "GRANT",
            "REVOKE",
            "EXECUTE",
            "EXPLAIN",
        ):
            raise ReadOnlyQueryError(f"Forbidden SQL construct: {kind}")

        # Check for function calls with dangerous names
        func_name = ""
        if hasattr(node, "name"):
            func_name = str(node.name).upper()
        if func_name in ("LOAD_FILE",):
            raise ReadOnlyQueryError(f"Forbidden function: {func_name}")

        # Check catalog references
        if hasattr(node, "db") and node.db and str(node.db) != database:
            raise ReadOnlyQueryError(f"Cross-database access denied: {node.db}")

    # Must be a SELECT (or WITH ... SELECT)
    root = parsed
    if hasattr(parsed, "ctes") and parsed.ctes:
        root = parsed.expression
    elif hasattr(parsed, "kind"):
        root_kind = str(parsed.kind).upper()
        if root_kind != "SELECT":
            raise ReadOnlyQueryError(f"Only SELECT allowed, got {root_kind}")
        return
    root_kind = root.key.upper() if hasattr(root, "key") else ""
    if root_kind and root_kind != "SELECT":
        raise ReadOnlyQueryError(f"Only SELECT allowed, got {root_kind}")


class MySQLCatalogProvider:
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database

    def _connect(self):
        import mysql.connector

        return mysql.connector.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            connect_timeout=5,
        )

    def list_tables(self) -> tuple[TableInfo, ...]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            return tuple(TableInfo(name=row[0]) for row in cursor.fetchall())
        finally:
            conn.close()

    def describe_table(self, table_name: str) -> QueryResult:
        _validate_table_name(table_name)
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE `{table_name}`")
            rows = cursor.fetchall()
            return QueryResult(
                columns=("Field", "Type", "Null", "Key", "Default", "Extra"),
                rows=tuple(rows),
                truncated=False,
            )
        finally:
            conn.close()

    def preview_table(self, table_name: str, *, limit: int = 20) -> QueryResult:
        _validate_table_name(table_name)
        limit = max(1, min(limit, 100))
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM `{table_name}` LIMIT {max(1, min(limit, 100))}"
            )
            columns = (
                tuple(d[0] for d in cursor.description) if cursor.description else ()
            )
            rows = cursor.fetchall()
            return QueryResult(
                columns=columns,
                rows=tuple(rows),
                truncated=len(rows) >= limit,
            )
        finally:
            conn.close()

    def execute_readonly(self, query: str, *, limit: int = 100) -> QueryResult:
        limit = max(1, min(limit, 1000))
        validate_readonly_query(query, database=self._database)
        conn = self._connect()
        try:
            cursor = conn.cursor()
            wrapped = (
                f"SELECT /*+ MAX_EXECUTION_TIME(5000) */ * "
                f"FROM ({query}) AS phase2_query LIMIT {max(1, min(limit, 1000))}"
            )
            cursor.execute(wrapped)
            columns = (
                tuple(d[0] for d in cursor.description) if cursor.description else ()
            )
            rows = cursor.fetchall()
            return QueryResult(
                columns=columns,
                rows=tuple(rows),
                truncated=len(rows) >= limit,
            )
        finally:
            conn.close()
