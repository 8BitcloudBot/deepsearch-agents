"""Controlled catalog SQL tools."""

import asyncio

from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.providers.contracts import CatalogProvider


def create_catalog_tools(provider: CatalogProvider, events: InMemoryEventBus):
    @tool
    async def list_sql_tables() -> str:
        """List all available tables in the research catalog."""
        result = await asyncio.to_thread(provider.list_tables)
        names = [t.name for t in result]
        return "Tables: " + ", ".join(names)

    @tool
    async def describe_table(table_name: str) -> str:
        """Show schema for a specific table."""
        result = await asyncio.to_thread(provider.describe_table, table_name)
        return f"Columns for {table_name}: {', '.join(result.columns)}"

    @tool
    async def preview_table(table_name: str) -> str:
        """Preview first 20 rows of a table."""
        result = await asyncio.to_thread(provider.preview_table, table_name)
        rows_str = "\n".join(str(r) for r in result.rows[:10])
        return f"Preview of {table_name}:\n{rows_str}"

    @tool
    async def execute_readonly_query(query: str) -> str:
        """Execute a read-only SELECT query. Returns tabular result."""
        result = await asyncio.to_thread(provider.execute_readonly, query)
        header = " | ".join(result.columns)
        rows = "\n".join(" | ".join(str(c) for c in r) for r in result.rows[:20])
        return f"{header}\n{'-' * len(header)}\n{rows}"

    return [
        list_sql_tables,
        describe_table,
        preview_table,
        execute_readonly_query,
    ]
