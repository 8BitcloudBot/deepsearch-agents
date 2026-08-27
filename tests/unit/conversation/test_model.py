import pytest

from app.conversation.model import ModelUnavailable, build_agent_model
from app.conversation.settings import ConversationSettings


def test_conversation_model_uses_openai_compatible_configuration(monkeypatch):
    calls: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    settings = ConversationSettings.from_env(
        {
            "MODEL_NAME": "gpt-compatible",
            "MODEL_BASE_URL": "https://gateway.example/v1",
            "MODEL_API_KEY": "model-secret",
            "MODEL_TIMEOUT_SECONDS": "17",
        }
    )

    model, descriptor = build_agent_model(settings)

    assert isinstance(model, FakeChatOpenAI)
    assert calls == {
        "model": "gpt-compatible",
        "api_key": "model-secret",
        "base_url": "https://gateway.example/v1",
        "timeout": 17.0,
        "max_retries": 2,
        "temperature": 0.2,
    }
    assert descriptor.model == "gpt-compatible"
    assert "model-secret" not in repr(descriptor)


def test_conversation_model_sampling_parameters_are_env_overridable(monkeypatch):
    calls: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    settings = ConversationSettings.from_env(
        {
            "MODEL_NAME": "gpt-compatible",
            "MODEL_API_KEY": "model-secret",
            "MODEL_TEMPERATURE": "0.7",
            "MODEL_TOP_P": "0.9",
            "MODEL_MAX_RETRIES": "5",
        }
    )

    build_agent_model(settings)

    assert calls["temperature"] == 0.7
    assert calls["top_p"] == 0.9
    assert calls["max_retries"] == 5


def test_conversation_model_omits_optional_params_when_none():
    settings = ConversationSettings(
        model_name="gpt-compatible",
        model_api_key="model-secret",
        model_temperature=None,
        model_top_p=None,
    )

    assert settings.model_temperature is None
    assert settings.model_top_p is None


def test_conversation_settings_reject_out_of_range_sampling_env():
    with pytest.raises(ValueError):
        ConversationSettings.from_env({"MODEL_TEMPERATURE": "1.5"})
    with pytest.raises(ValueError):
        ConversationSettings.from_env({"MODEL_MAX_RETRIES": "-1"})


def test_conversation_model_requires_api_key():
    with pytest.raises(ModelUnavailable) as error:
        build_agent_model(ConversationSettings.from_env({}))

    assert error.value.code == "model-authentication"
