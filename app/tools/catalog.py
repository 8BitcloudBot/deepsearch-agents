"""Controlled catalog SQL tools with thread-aware events."""

import asyncio

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.api.events import InMemoryEventBus
from app.providers.contracts import CatalogProvider


def _tid(c: RunnableConfig) -> str:
    t = c.get("configurable", {}).get("thread_id")
    if not isinstance(t, str) or not t:
        raise ValueError("RunnableConfig.configurable.thread_id required")
    return t


def _emit(ev, tid, phase, msg, tn):
    ev.emit(tid, phase, msg, {"tool_name": tn})


def create_catalog_tools(p: CatalogProvider, ev: InMemoryEventBus):
    @tool
    async def list_sql_tables(config: RunnableConfig) -> str:
        tid = _tid(config)
        _emit(ev, tid, "tool_started", "list", "list_sql_tables")
        r = await asyncio.to_thread(p.list_tables)
        _emit(ev, tid, "tool_completed", f"found {len(r)}", "list_sql_tables")
        return "Tables: " + ", ".join(t.name for t in r)

    @tool
    async def describe_table(tn: str, config: RunnableConfig) -> str:
        tid = _tid(config)
        _emit(ev, tid, "tool_started", tn, "describe_table")
        r = await asyncio.to_thread(p.describe_table, tn)
        _emit(ev, tid, "tool_completed", tn, "describe_table")
        return f"Columns for {tn}: {', '.join(r.columns)}"

    @tool
    async def preview_table(tn: str, config: RunnableConfig) -> str:
        tid = _tid(config)
        _emit(ev, tid, "tool_started", tn, "preview_table")
        r = await asyncio.to_thread(p.preview_table, tn)
        _emit(ev, tid, "tool_completed", tn, "preview_table")
        rows_str = "\n".join(str(row) for row in r.rows[:10])
        return f"Preview of {tn}:\n{rows_str}"

    @tool
    async def execute_readonly_query(q: str, config: RunnableConfig) -> str:
        tid = _tid(config)
        _emit(ev, tid, "tool_started", "query", "execute_readonly_query")
        r = await asyncio.to_thread(p.execute_readonly, q)
        _emit(ev, tid, "tool_completed", "done", "execute_readonly_query")
        hdr = " | ".join(r.columns)
        rows = "\n".join(" | ".join(str(c) for c in row) for row in r.rows[:20])
        return f"{hdr}\n{'-' * len(hdr)}\n{rows}"

    return [list_sql_tables, describe_table, preview_table, execute_readonly_query]
