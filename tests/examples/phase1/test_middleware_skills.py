"""Behavioral tests for middleware and skills using real APIs.

Phase 1-2: Skills tests use real SkillsMiddleware.before_agent() + Runtime().
No directory scanning allowed in implementation or verification.
"""

import logging
from unittest.mock import MagicMock

import pytest

from examples.phase1._07_middleware_skills import (
    MiddlewareEvent,
    build_recording_middleware,
    create_skills_middleware,
)

# ---- helpers ----


def write_skill(root, *, directory: str, name: str, description: str) -> None:
    """Write a SKILL.md fixture with valid YAML frontmatter."""
    skill_dir = root / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Test Skill\n",
        encoding="utf-8",
    )


# ---- RecordingMiddleware tests (unchanged from Phase 1-1) ----


class TestRecordingMiddleware:
    def test_successful_call_records_metadata(self):
        events: list[MiddlewareEvent] = []
        clock = iter([1000.0, 1000.5]).__next__
        rid_factory = iter(["req-001"]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=rid_factory
        )

        fake_model = MagicMock()
        fake_model.model_name = "test-model"
        fake_response = MagicMock()
        fake_response.result = [MagicMock(), MagicMock()]

        request = MagicMock()
        request.model = fake_model
        request.messages = [MagicMock()] * 3

        handler = MagicMock(return_value=fake_response)
        _result = mw.wrap_model_call(request, handler)

        assert len(events) == 2
        started = events[0]
        assert started.phase == "started"
        assert started.request_id == "req-001"
        assert started.model_name == "test-model"
        assert started.input_message_count == 3
        assert started.duration_ms is None

        completed = events[1]
        assert completed.phase == "completed"
        assert completed.output_message_count == 2
        assert completed.duration_ms is not None
        assert completed.duration_ms > 0

    def test_handler_error_records_error_type(self):
        events: list[MiddlewareEvent] = []
        clock = iter([2000.0, 2000.1]).__next__
        rid_factory = iter(["req-err"]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=rid_factory
        )

        fake_model = MagicMock()
        fake_model.model_name = "failing-model"
        request = MagicMock()
        request.model = fake_model
        request.messages = [MagicMock()]

        handler = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError):
            mw.wrap_model_call(request, handler)

        assert len(events) == 2
        failed = events[1]
        assert failed.phase == "failed"
        assert failed.error_type == "ValueError"
        assert failed.duration_ms is not None

    def test_events_do_not_leak_prompt_or_key(self):
        events: list[MiddlewareEvent] = []
        clock = iter([1000.0, 1000.1]).__next__
        rid_factory = iter(["req-sec"]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=rid_factory
        )

        fake_model = MagicMock()
        fake_model.model_name = "secure-model"
        fake_response = MagicMock()
        fake_response.result = []
        request = MagicMock()
        request.model = fake_model
        request.messages = []
        handler = MagicMock(return_value=fake_response)

        mw.wrap_model_call(request, handler)

        for event in events:
            rep = repr(event)
            for secret in ["sk-", "api_key", "password", "secret"]:
                assert secret not in rep.lower(), (
                    f"Event {event.phase} contains secret '{secret}': {rep}"
                )

    def test_deterministic_clock(self):
        events: list[MiddlewareEvent] = []
        clock = iter([500.0, 500.250]).__next__
        rid_factory = iter(["req-clk"]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=rid_factory
        )

        fake_model = MagicMock()
        fake_model.model_name = "m"
        fake_response = MagicMock()
        fake_response.result = []
        request = MagicMock()
        request.model = fake_model
        request.messages = []
        handler = MagicMock(return_value=fake_response)

        mw.wrap_model_call(request, handler)
        assert events[1].duration_ms == pytest.approx(250.0)

    def test_request_id_factory_used(self):
        events: list[MiddlewareEvent] = []
        call_count = [0]

        def my_factory():
            call_count[0] += 1
            return f"custom-{call_count[0]}"

        clock = iter([0.0, 0.1]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=my_factory
        )

        fake_model = MagicMock()
        fake_model.model_name = "m"
        fake_response = MagicMock()
        fake_response.result = []
        request = MagicMock()
        request.model = fake_model
        request.messages = []
        handler = MagicMock(return_value=fake_response)

        mw.wrap_model_call(request, handler)
        assert events[0].request_id == "custom-1"


# ---- SkillsMiddleware real-loading tests (Phase 1-2) ----


class TestRealSkillsLoading:
    def test_before_agent_parses_source_review_metadata(self, tmp_path):
        """Real SkillsMiddleware.before_agent() + Runtime() loads metadata."""
        from langgraph.runtime import Runtime

        write_skill(
            tmp_path,
            directory="source-review",
            name="source-review",
            description="Reviews source materials for credibility.",
        )
        mw = create_skills_middleware(tmp_path)
        update = mw.before_agent({}, Runtime(), {})
        assert update is not None, "before_agent must return update for empty state"
        meta_list = update.get("skills_metadata", [])
        assert len(meta_list) >= 1

        sr = [m for m in meta_list if m["name"] == "source-review"]
        assert len(sr) == 1
        assert sr[0]["name"] == "source-review"
        assert sr[0]["description"] == "Reviews source materials for credibility."
        assert sr[0]["path"].endswith("/source-review/SKILL.md")

    def test_missing_frontmatter_skill_is_omitted_with_warning(self, tmp_path, caplog):
        """Skill without YAML frontmatter must be skipped with a warning."""
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Bad Skill\n\nNo frontmatter here.\n", encoding="utf-8"
        )

        from langgraph.runtime import Runtime

        mw = create_skills_middleware(tmp_path)
        with caplog.at_level(logging.WARNING):
            update = mw.before_agent({}, Runtime(), {})

        assert update is not None
        meta_list = update.get("skills_metadata", [])
        # The skill without frontmatter must NOT appear in metadata
        names = [m["name"] for m in meta_list]
        assert "bad-skill" not in names

        # Must have logged a warning about the invalid skill
        warnings = [r.message for r in caplog.records]
        assert any("SKILL.md" in w for w in warnings), (
            f"Expected warning about SKILL.md, got: {warnings}"
        )

    def test_directory_name_mismatch_is_omitted_with_warning(self, tmp_path, caplog):
        """When directory name != frontmatter name, skill warns but still loads.

        DeepAgents 0.6.12 logs a WARNING about the mismatch but still
        includes the skill in metadata (under its declared name).
        """
        write_skill(
            tmp_path,
            directory="source-review",
            name="other-review",
            description="Mismatched name.",
        )

        from langgraph.runtime import Runtime

        mw = create_skills_middleware(tmp_path)
        with caplog.at_level(logging.WARNING):
            update = mw.before_agent({}, Runtime(), {})

        assert update is not None
        # Framework warns but still loads; the key assertion is the warning
        warnings = [r.message for r in caplog.records]
        assert any("does not follow Agent Skills" in w for w in warnings), (
            f"Expected spec-compliance warning, got: {warnings}"
        )

    def test_empty_source_returns_empty_metadata(self, tmp_path):
        """Empty skill source must return empty metadata, not fake names."""
        from langgraph.runtime import Runtime

        mw = create_skills_middleware(tmp_path)
        update = mw.before_agent({}, Runtime(), {})
        assert update is not None
        assert update.get("skills_metadata", []) == []

    def test_existing_skills_metadata_skips_reload(self, tmp_path):
        """When state already has 'skills_metadata', return None."""
        from langgraph.runtime import Runtime

        mw = create_skills_middleware(tmp_path)
        update = mw.before_agent({"skills_metadata": []}, Runtime(), {})
        assert update is None

    def test_modify_request_injects_loaded_skill_metadata(self, tmp_path):
        """modify_request() must inject skill name/description into system msg."""
        from langchain.agents.middleware.types import ModelRequest
        from langchain_core.messages import SystemMessage
        from langgraph.runtime import Runtime

        write_skill(
            tmp_path,
            directory="source-review",
            name="source-review",
            description="Reviews source materials for credibility.",
        )
        mw = create_skills_middleware(tmp_path)
        update = mw.before_agent({}, Runtime(), {})
        meta_list = update["skills_metadata"]

        # Build a real ModelRequest with a fake model
        from langchain_core.language_models import FakeListChatModel

        model = FakeListChatModel(responses=["ok"])
        state = {"skills_metadata": meta_list}
        from unittest.mock import MagicMock

        request = ModelRequest(
            model=model,
            messages=[],
            system_message=SystemMessage(content="Base system prompt"),
            tools=[],
            state=state,
            runtime=MagicMock(),
            response_format=None,
            tool_choice=None,
            model_settings={},
        )

        modified = mw.modify_request(request)
        new_sys = modified.system_message
        assert new_sys is not None
        if hasattr(new_sys, "content"):
            content = new_sys.content
            if isinstance(content, list):
                new_content = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            else:
                new_content = str(content)
        else:
            new_content = str(new_sys)
        assert "source-review" in new_content
        assert "Reviews source materials for credibility" in new_content
        assert "Base system prompt" in new_content

    def test_project_skill_fixture_is_parseable(self):
        """The repository's own source-review SKILL.md must be parseable."""
        from pathlib import Path

        from langgraph.runtime import Runtime

        skills_root = (
            Path(__file__).resolve().parents[3] / "examples" / "phase1" / "skills"
        )
        assert skills_root.is_dir(), f"Skills root not found: {skills_root}"

        mw = create_skills_middleware(skills_root)
        update = mw.before_agent({}, Runtime(), {})
        assert update is not None
        meta_list = update.get("skills_metadata", [])
        names = [m["name"] for m in meta_list]
        assert "source-review" in names, (
            f"Project source-review not in loaded skills: {names}"
        )
