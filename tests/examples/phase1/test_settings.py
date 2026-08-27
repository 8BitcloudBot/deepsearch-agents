"""Tests for examples.phase1.settings."""

import pytest

from examples.phase1.settings import Phase1Settings, load_settings, require_api_key


def test_default_model_name():
    settings = load_settings()
    assert settings.model_name == "openai:gpt-4.1-mini"


def test_default_base_url_is_none():
    settings = load_settings()
    assert settings.base_url is None


def test_default_api_key_is_none():
    settings = load_settings()
    assert settings.api_key is None


def test_default_timeout():
    settings = load_settings()
    assert settings.timeout_seconds == 60.0


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "anthropic:claude-sonnet")
    monkeypatch.setenv("MODEL_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("MODEL_API_KEY", "sk-test-key")  # pragma: allowlist secret
    monkeypatch.setenv("MODEL_TIMEOUT_SECONDS", "30")
    settings = load_settings()
    assert settings.model_name == "anthropic:claude-sonnet"
    assert settings.base_url == "https://api.example.com"
    assert settings.api_key == "sk-test-key"  # pragma: allowlist secret
    assert settings.timeout_seconds == 30.0


def test_require_api_key_returns_key():
    settings = Phase1Settings(
        model_name="test",
        base_url=None,
        api_key="sk-abc123",  # pragma: allowlist secret
        timeout_seconds=60,
    )
    key = require_api_key(settings)
    assert key == "sk-abc123"  # pragma: allowlist secret


def test_require_api_key_raises_when_missing():
    settings = Phase1Settings(
        model_name="test",
        base_url=None,
        api_key=None,
        timeout_seconds=60,
    )
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        require_api_key(settings)


def test_require_api_key_raises_when_empty():
    settings = Phase1Settings(
        model_name="test",
        base_url=None,
        api_key="",
        timeout_seconds=60,
    )
    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        require_api_key(settings)


def test_error_message_does_not_leak_key():
    """Error messages must NOT contain any API key value."""
    settings = Phase1Settings(
        model_name="test",
        base_url=None,
        api_key=None,
        timeout_seconds=60,
    )
    with pytest.raises(RuntimeError) as exc:
        require_api_key(settings)
    # The message should reference the env var, not any key value
    assert "MODEL_API_KEY" in str(exc.value)
    assert "sk-" not in str(exc.value).lower()


def test_timeout_must_be_positive():
    with pytest.raises(ValueError):
        Phase1Settings(
            model_name="test", base_url=None, api_key=None, timeout_seconds=0
        )
    with pytest.raises(ValueError):
        Phase1Settings(
            model_name="test", base_url=None, api_key=None, timeout_seconds=-1
        )


def test_timeout_non_numeric_rejected():
    """Non-numeric MODEL_TIMEOUT_SECONDS should be rejected."""
    with pytest.raises(ValueError):
        Phase1Settings(
            model_name="test",
            base_url=None,
            api_key=None,
            timeout_seconds="abc",  # type: ignore[arg-type]
        )


def test_settings_frozen():
    settings = Phase1Settings(
        model_name="test", base_url=None, api_key=None, timeout_seconds=60
    )
    with pytest.raises(Exception):  # FrozenInstanceError or similar
        settings.model_name = "changed"  # type: ignore[misc]
