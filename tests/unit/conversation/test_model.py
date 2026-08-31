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
            "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret — 测试假值
            "MODEL_TIMEOUT_SECONDS": "17",
        }
    )

    model, descriptor = build_agent_model(settings)

    assert isinstance(model, FakeChatOpenAI)
    assert calls == {
        "model": "gpt-compatible",
        "api_key": "model-secret",  # pragma: allowlist secret
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
            "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret — 测试假值
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
        model_api_key="model-secret",  # pragma: allowlist secret
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


def test_build_agent_model_supports_name_override(monkeypatch):
    calls: dict[str, object] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            calls.update(kwargs)

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChatOpenAI)
    settings = ConversationSettings.from_env(
        {"MODEL_NAME": "main-model", "MODEL_API_KEY": "k"}  # pragma: allowlist secret
    )

    _, descriptor = build_agent_model(settings, model_name_override="lite-model")

    assert calls["model"] == "lite-model"
    assert descriptor.model == "lite-model"
    # 未覆写时保持主模型名
    _, descriptor_main = build_agent_model(settings)
    assert descriptor_main.model == "main-model"


def test_model_name_light_setting_parses():
    settings = ConversationSettings.from_env({"MODEL_NAME_LIGHT": "lite-model"})
    assert settings.model_name_light == "lite-model"
    assert ConversationSettings.from_env({}).model_name_light is None
