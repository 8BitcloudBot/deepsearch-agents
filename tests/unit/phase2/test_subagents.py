"""Tests for subagent builder."""

from app.agent.subagents import build_tutorial_subagents


class TestSubagentBuilder:
    def test_builds_three_subagents(self):
        subs = build_tutorial_subagents(
            web_tools=[lambda x: x],
            catalog_tools=[lambda x: x],
            knowledge_tools=[lambda x: x],
        )
        assert len(subs) == 3

    def test_subagent_names(self):
        subs = build_tutorial_subagents([], [], [])
        names = [s["name"] for s in subs]
        assert names == ["web-research", "structured-data", "knowledge-base"]

    def test_tools_are_callable(self):
        def fake_tool():
            pass

        subs = build_tutorial_subagents(
            web_tools=[fake_tool],
            catalog_tools=[],
            knowledge_tools=[],
        )
        assert callable(subs[0]["tools"][0])
