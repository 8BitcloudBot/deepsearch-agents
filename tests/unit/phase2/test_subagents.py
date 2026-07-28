"""Tests for subagent definitions and tool assignments."""

from app.agent.subagents import (
    KNOWLEDGE_BASE,
    STRUCTURED_DATA,
    TUTORIAL_SUBAGENTS,
    WEB_RESEARCH,
)


class TestSubagentDefinitions:
    def test_web_research_name_and_tools(self):
        assert WEB_RESEARCH["name"] == "web-research"
        assert "internet_search" in WEB_RESEARCH["tools"]

    def test_structured_data_name_and_tools(self):
        assert STRUCTURED_DATA["name"] == "structured-data"
        assert "list_sql_tables" in STRUCTURED_DATA["tools"]
        assert "execute_readonly_query" in STRUCTURED_DATA["tools"]

    def test_knowledge_base_name_and_tools(self):
        assert KNOWLEDGE_BASE["name"] == "knowledge-base"
        assert "ask_knowledge_assistant" in KNOWLEDGE_BASE["tools"]

    def test_all_three_in_tuple(self):
        assert len(TUTORIAL_SUBAGENTS) == 3
        names = [s["name"] for s in TUTORIAL_SUBAGENTS]
        assert names == ["web-research", "structured-data", "knowledge-base"]
