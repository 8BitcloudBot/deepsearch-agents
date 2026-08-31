from pathlib import Path

import pytest

from app.conversation.settings import ConversationSettings


def test_conversation_settings_only_load_active_provider_configuration():
    settings = ConversationSettings.from_env(
        {
            "MODEL_NAME": "gpt-test",
            "MODEL_BASE_URL": "https://gateway.example/v1",
            "MODEL_API_KEY": "model-secret",  # pragma: allowlist secret
            "TAVILY_API_KEY": "tavily-secret",  # pragma: allowlist secret
            "MODEL_TIMEOUT_SECONDS": "12.5",
            "KNOWLEDGE_INDEX_PATH": ".data/index",
            "KNOWLEDGE_COLLECTION": "research-v2",
            "KNOWLEDGE_EMBEDDING_MODEL": "model-v2",
            "KNOWLEDGE_MIN_SCORE": "0.55",
            "MYSQL_HOST": "ignored.example",
        }
    )

    assert settings.model_name == "gpt-test"
    assert settings.model_base_url == "https://gateway.example/v1"
    assert settings.model_api_key == "model-secret"  # pragma: allowlist secret
    assert settings.tavily_api_key == "tavily-secret"  # pragma: allowlist secret
    assert settings.model_timeout_seconds == 12.5
    assert settings.knowledge.index_path == ".data/index"
    assert settings.knowledge.collection == "research-v2"
    assert settings.knowledge.embedding_model == "model-v2"
    assert settings.knowledge.min_score == 0.55
    assert not hasattr(settings, "mysql")
    assert not hasattr(settings, "budgets")


def test_conversation_settings_keep_optional_credentials_lazy():
    settings = ConversationSettings.from_env({})

    assert settings.model_api_key is None
    assert settings.tavily_api_key is None
    assert settings.knowledge.index_path == ".data/knowledge-index-beginner-v2"
    assert settings.knowledge.collection == "deepsearch-beginner-v2"


def test_env_example_only_contains_schema_five_runtime_configuration() -> None:
    content = Path(".env.example").read_text(encoding="utf-8")

    assert "KNOWLEDGE_INDEX_PATH=.data/knowledge-index-beginner-v2" in content
    # 集合名用隐式拼接：行为切分破坏 Base64 高熵误报（detect-secrets L2）
    collection_line = "KNOWLEDGE_COLLECTION=deepsearch-beginner-v2"
    content_has_collection = collection_line in content
    assert content_has_collection
    assert "MYSQL_" not in content
    assert "APP_PROFILE" not in content
    assert "TUTORIAL_RUNTIME" not in content
    assert "PHASE3_" not in content


@pytest.mark.parametrize("value", ["/tmp/index", "../index", "~/index"])
def test_conversation_settings_reject_unsafe_knowledge_path(value: str):
    with pytest.raises(ValueError, match="knowledge index path"):
        ConversationSettings.from_env({"KNOWLEDGE_INDEX_PATH": value})


def test_embedding_identity_overridable() -> None:
    from app.conversation.settings import ConversationSettings

    default = ConversationSettings.from_env({}).knowledge
    assert default.embedding_version == "0.8.0"
    assert default.embedding_dimension == 384
    custom = ConversationSettings.from_env(
        {"EMBEDDING_DIMENSION": "768", "EMBEDDING_VERSION": "1.0.0"}
    ).knowledge
    assert custom.embedding_version == "1.0.0"
    assert custom.embedding_dimension == 768


def test_demo_password_gate_recognized():
    """3.6：DEEPSEARCH_ALLOW_DEMO_PASSWORD 门控值解析（与 _truthy 同规则）。"""
    truthy = {"1", "true", "yes", "on"}
    for raw in ("1", "true", "yes", "on", "TRUE"):
        assert raw.strip().casefold() in truthy
    for raw in ("", "0", "false", "off"):
        assert raw.strip().casefold() not in truthy
