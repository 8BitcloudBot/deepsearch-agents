"""Behavioral tests for middleware and skills using real APIs.

No MODEL_API_KEY required.
"""

from unittest.mock import MagicMock

import pytest

from examples.phase1._07_middleware_skills import (
    MiddlewareEvent,
    build_recording_middleware,
    create_skills_middleware,
    list_loaded_skill_names,
)


class TestRecordingMiddleware:
    def test_successful_call_records_metadata(self):
        """Successful handler call records started + completed events."""
        events: list[MiddlewareEvent] = []
        clock = iter([1000.0, 1000.5]).__next__  # 500ms later
        rid_factory = iter(["req-001"]).__next__

        mw = build_recording_middleware(
            events=events, clock=clock, request_id_factory=rid_factory
        )

        # Build a mock request and handler
        fake_model = MagicMock()
        fake_model.model_name = "test-model"
        fake_response = MagicMock()
        fake_response.result = [MagicMock(), MagicMock()]  # 2 output msgs

        request = MagicMock()
        request.model = fake_model
        request.messages = [MagicMock()] * 3  # 3 input msgs

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
        """Handler exception records phase=failed with error_type."""
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
        """MiddlewareEvent repr must not contain prompt or key text."""
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
        request.messages = [MagicMock()]
        handler = MagicMock(return_value=fake_response)

        mw.wrap_model_call(request, handler)

        for event in events:
            rep = repr(event)
            for secret in ["sk-", "api_key", "password", "secret"]:
                assert secret not in rep.lower(), (
                    f"Event {event.phase} contains secret '{secret}': {rep}"
                )

    def test_deterministic_clock(self):
        """Fixed clock values produce exact duration."""
        events: list[MiddlewareEvent] = []
        clock = iter([500.0, 500.250]).__next__  # exactly 250ms
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
        """Custom request_id_factory produces the expected ID."""
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


class TestSkillsLoading:
    def test_source_review_skill_discovered(self, tmp_path):
        """SkillsMiddleware must discover source-review from SKILL.md."""
        skill_dir = tmp_path / "source-review"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# source-review\n\n**Description:** Reviews sources.\n\n"
            "**Trigger:** verify.\n"
        )

        mw = create_skills_middleware(tmp_path)
        names = list_loaded_skill_names(mw)
        assert "source-review" in names, f"Expected source-review in {names}"

    def test_missing_skill_dir_no_error(self, tmp_path):
        """SkillsMiddleware with empty dir must not crash."""
        mw = create_skills_middleware(tmp_path)
        names = list_loaded_skill_names(mw)
        assert isinstance(names, list)
