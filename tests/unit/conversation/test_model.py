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
        "max_retries": 0,
    }
    assert descriptor.model == "gpt-compatible"
    assert "model-secret" not in repr(descriptor)


def test_conversation_model_requires_api_key():
    with pytest.raises(ModelUnavailable) as error:
        build_agent_model(ConversationSettings.from_env({}))

    assert error.value.code == "model-authentication"
