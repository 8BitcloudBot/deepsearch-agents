"""Phase 2-2 remediation RED tests."""

import pytest


class TestRAGFlowAskGenerator:
    def test_success_path_yields_final_message(self):
        """Session.ask(stream=False) is a generator; must iterate to get content."""
        from unittest.mock import MagicMock, PropertyMock

        from app.providers.ragflow import RAGFlowKnowledgeProvider

        fake_msg = MagicMock()
        type(fake_msg).content = PropertyMock(return_value="final answer text")
        fake_session = MagicMock()
        fake_session.id = "sess-1"
        fake_session.ask.return_value = iter([fake_msg])  # generator

        fake_chat = MagicMock()
        fake_chat.name = "test"
        fake_chat.id = "chat-1"
        fake_chat.create_session.return_value = fake_session

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "ragflow_sdk.RAGFlow",
                lambda *a, **kw: MagicMock(list_chats=lambda: [fake_chat]),
            )
            provider = RAGFlowKnowledgeProvider(
                api_key="k",  # pragma: allowlist secret
                base_url="http://x",
            )  # pragma: allowlist secret
            answer = provider.ask("test", "question")
            assert answer.answer == "final answer text"
            fake_chat.delete_sessions.assert_called_once_with(["sess-1"])

    def test_error_path_still_deletes_session(self):
        """Session cleanup on error: delete_sessions called even when ask raises."""
        from unittest.mock import MagicMock

        from app.providers.ragflow import RAGFlowKnowledgeProvider

        fake_session = MagicMock()
        fake_session.id = "sess-err"
        fake_session.ask.side_effect = RuntimeError("boom")

        fake_chat = MagicMock()
        fake_chat.name = "test"
        fake_chat.id = "chat-1"
        fake_chat.create_session.return_value = fake_session

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "ragflow_sdk.RAGFlow",
                lambda *a, **kw: MagicMock(list_chats=lambda: [fake_chat]),
            )
            provider = RAGFlowKnowledgeProvider(
                api_key="k",  # pragma: allowlist secret
                base_url="http://x",
            )  # pragma: allowlist secret
            with pytest.raises(RuntimeError):
                provider.ask("test", "question")
            fake_chat.delete_sessions.assert_called_once_with(["sess-err"])


class TestSubagentBuilder:
    def test_subagents_use_real_tool_objects(self):
        """Subagent builder must inject real LangChain tool callables, not strs."""
        from app.agent.subagents import build_tutorial_subagents

        def fake_tool():
            pass

        subs = build_tutorial_subagents(
            web_tools=[fake_tool],
            catalog_tools=[],
            knowledge_tools=[],
        )
        for sub in subs:
            tools = sub["tools"]
            assert isinstance(tools, list)
            for tool in tools:
                assert callable(tool), (
                    f"Subagent {sub['name']} tool {tool!r} is not callable"
                )


class TestProviderEnumValidation:
    def test_app_profile_only_tutorial(self):
        from app.settings import Phase2Settings

        with pytest.raises(ValueError):
            Phase2Settings.from_env({"APP_PROFILE": "agent-research"})

    def test_web_provider_only_mock_or_tavily(self):
        from app.settings import Phase2Settings

        with pytest.raises(ValueError, match="WEB_PROVIDER"):
            Phase2Settings.from_env({"WEB_PROVIDER": "ragflow"})

    def test_catalog_provider_only_mock_or_mysql(self):
        from app.settings import Phase2Settings

        with pytest.raises(ValueError, match="CATALOG_PROVIDER"):
            Phase2Settings.from_env({"CATALOG_PROVIDER": "tavily"})

    def test_knowledge_provider_only_mock_or_ragflow(self):
        from app.settings import Phase2Settings

        with pytest.raises(ValueError, match="KNOWLEDGE_PROVIDER"):
            Phase2Settings.from_env({"KNOWLEDGE_PROVIDER": "mysql"})

    def test_mysql_user_must_be_tutorial_reader(self):
        from app.providers.factory import build_providers
        from app.settings import Phase2Settings

        settings = Phase2Settings.from_env(
            {
                "CATALOG_PROVIDER": "mysql",
                "MYSQL_USER": "root",
            }
        )
        with pytest.raises(ValueError, match="tutorial_reader"):
            build_providers(settings)


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


class TestEventBusOverflow:
    def test_data_is_json_value(self):
        """TutorialEvent.data must accept only JsonValue-compatible values."""
        from app.api.events import InMemoryEventBus

        bus = InMemoryEventBus()
        event = bus.emit("t", "task_started", "m", {"key": "value", "num": 42})
        assert isinstance(event.data, dict)
        assert event.data["key"] == "value"
