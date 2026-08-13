"""P4.5-3 fail-closed showcase configuration and credential-read tests."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.showcase.config import ShowcaseRuntimeConfig  # noqa: E402

MODEL_KEY = "MODEL_API_KEY"
TAVILY_KEY = "TAVILY_API_KEY"
MYSQL_KEY = "MYSQL_PASSWORD"
CREDENTIAL_KEYS = frozenset({MODEL_KEY, TAVILY_KEY, MYSQL_KEY})


class GuardedEnvironment(Mapping[str, str]):
    def __init__(self, values: Mapping[str, str], *, allowed: set[str] | None = None):
        self._values = dict(values)
        self._allowed = set(allowed or ())
        self.accessed: set[str] = set()

    def __getitem__(self, key: str) -> str:
        if key in CREDENTIAL_KEYS:
            self.accessed.add(key)
            if key not in self._allowed:
                raise AssertionError(f"credential key {key} must not be read")
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: str, default: str | None = None) -> str | None:
        if key in CREDENTIAL_KEYS:
            self.accessed.add(key)
            if key not in self._allowed:
                raise AssertionError(f"credential key {key} must not be read")
        return self._values.get(key, default)


def test_no_opt_in_reads_no_model_or_provider_credentials():
    env = GuardedEnvironment(
        {
            MODEL_KEY: "model-secret",
            TAVILY_KEY: "web-secret",
            MYSQL_KEY: "mysql-secret",
        }
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    assert config.capabilities.enabled is False
    assert config.model_available is False
    assert env.accessed == set()


def test_exact_opt_in_reads_only_model_and_declared_web_credentials():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "web",
            "WEB_PROVIDER": "tavily",
            MODEL_KEY: "model-secret",
            TAVILY_KEY: "web-secret",
            MYSQL_KEY: "mysql-secret",
        },
        allowed={MODEL_KEY, TAVILY_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    assert config.model_available is True
    assert config.web_provider == "tavily"
    assert config.tavily_api_key == "web-secret"  # pragma: allowlist secret
    assert config.catalog_provider is None
    assert config.knowledge_provider is None
    assert env.accessed == {MODEL_KEY, TAVILY_KEY}


def test_missing_model_is_a_limitation_not_an_exception():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "uploaded-file",
        },
        allowed={MODEL_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    assert config.model_available is False
    assert any(item.code == "model-unavailable" for item in config.limitations)
    assert env.accessed == {MODEL_KEY}


def test_missing_tavily_key_disables_only_web_without_leaking_key_name_value():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "web,uploaded-file",
            "WEB_PROVIDER": "tavily",
            MODEL_KEY: "model-secret",
        },
        allowed={MODEL_KEY, TAVILY_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    web_limitations = [item for item in config.limitations if item.source_kind == "web"]
    assert any(item.code == "configuration-missing" for item in web_limitations)
    assert all("model-secret" not in item.message for item in config.limitations)


def test_invalid_mysql_port_and_user_become_redacted_source_limitations():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "mysql",
            "CATALOG_PROVIDER": "mysql",
            "MYSQL_PORT": "not-a-port",
            "MYSQL_USER": "admin",
            MYSQL_KEY: "mysql-secret",
            MODEL_KEY: "model-secret",
        },
        allowed={MODEL_KEY, MYSQL_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    mysql_limitations = [
        item for item in config.limitations if item.source_kind == "mysql"
    ]
    assert mysql_limitations
    assert all("mysql-secret" not in item.message for item in mysql_limitations)
    assert config.mysql_port is None


def test_declared_knowledge_reads_only_local_index_configuration_and_model():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "knowledge",
            "KNOWLEDGE_PROVIDER": "qdrant-local",
            "KNOWLEDGE_INDEX_PATH": ".data/test-index",
            "KNOWLEDGE_COLLECTION": "test-collection",
            MODEL_KEY: "model-secret",
        },
        allowed={MODEL_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    assert config.knowledge_provider == "qdrant-local"
    assert config.knowledge_index_path == ".data/test-index"
    assert config.knowledge_collection == "test-collection"
    assert config.knowledge_chunking_version == "semantic-markdown-v1"
    assert config.knowledge_min_score == 0.4
    assert env.accessed == {MODEL_KEY}


def test_config_repr_never_exposes_credentials():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "web",
            "WEB_PROVIDER": "tavily",
            MODEL_KEY: "model-sentinel",
            TAVILY_KEY: "tavily-sentinel",
        },
        allowed={MODEL_KEY, TAVILY_KEY},
    )
    rendered = repr(ShowcaseRuntimeConfig.from_env(env))

    assert "model-sentinel" not in rendered
    assert "tavily-sentinel" not in rendered


def test_blank_model_name_fails_closed_before_source_credentials_are_read():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "web",
            "MODEL_NAME": "   ",
            MODEL_KEY: "model-secret",
            TAVILY_KEY: "must-not-be-read",
        },
        allowed={MODEL_KEY},
    )
    config = ShowcaseRuntimeConfig.from_env(env)

    assert config.model_available is False
    assert any(item.code == "model-unavailable" for item in config.limitations)
    assert env.accessed == {MODEL_KEY}


def test_mysql_host_and_database_validation_is_source_scoped():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "mysql",
            "CATALOG_PROVIDER": "mysql",
            "MYSQL_HOST": "   ",
            "MYSQL_DATABASE": "bad database",
            MODEL_KEY: "model-secret",
            MYSQL_KEY: "mysql-secret",
        },
        allowed={MODEL_KEY, MYSQL_KEY},
    )

    config = ShowcaseRuntimeConfig.from_env(env)

    assert any(
        item.code == "configuration-invalid" and item.source_kind == "mysql"
        for item in config.limitations
    )


def test_knowledge_index_path_rejects_absolute_paths():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "knowledge",
            "KNOWLEDGE_PROVIDER": "qdrant-local",
            "KNOWLEDGE_INDEX_PATH": "/tmp/knowledge-index",
            MODEL_KEY: "model-secret",
        },
        allowed={MODEL_KEY},
    )

    config = ShowcaseRuntimeConfig.from_env(env)

    assert any(
        item.code == "configuration-invalid" and item.source_kind == "knowledge"
        for item in config.limitations
    )


def test_knowledge_rejects_invalid_min_score_without_leaking_value():
    env = GuardedEnvironment(
        {
            "SHOWCASE_ENABLED": "1",
            "SHOWCASE_SOURCES": "knowledge",
            "KNOWLEDGE_PROVIDER": "qdrant-local",
            "KNOWLEDGE_MIN_SCORE": "not-a-number /Users/private",
            MODEL_KEY: "model-secret",
        },
        allowed={MODEL_KEY},
    )

    config = ShowcaseRuntimeConfig.from_env(env)

    assert any(
        item.code == "configuration-invalid" and item.source_kind == "knowledge"
        for item in config.limitations
    )
    assert all("/Users/private" not in item.message for item in config.limitations)
