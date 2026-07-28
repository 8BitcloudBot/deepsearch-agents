"""Phase 2 immutable settings."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

VALID_RUNTIMES = frozenset({"mock", "deepagents"})
VALID_PROVIDERS = frozenset({"mock", "tavily", "mysql", "ragflow"})


@dataclass(frozen=True)
class Phase2Settings:
    app_profile: str = "tutorial"
    tutorial_runtime: str = "mock"
    web_provider: str = "mock"
    catalog_provider: str = "mock"
    knowledge_provider: str = "mock"
    model_name: str = "openai:gpt-4.1-mini"
    model_base_url: str | None = None
    model_api_key: str | None = None
    tavily_api_key: str | None = None
    ragflow_base_url: str | None = None
    ragflow_api_key: str | None = None
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "tutorial_reader"
    mysql_password: str = "tutorial_reader"
    mysql_database: str = "research_copilot"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Phase2Settings":
        env = environ if environ is not None else os.environ

        def _get(key: str, default: str = "") -> str:
            return env.get(key, default)

        runtime = _get("TUTORIAL_RUNTIME", "mock")
        if runtime not in VALID_RUNTIMES:
            raise ValueError(
                f"TUTORIAL_RUNTIME must be one of {sorted(VALID_RUNTIMES)}, "
                f"got {runtime!r}"
            )

        web = _get("WEB_PROVIDER", "mock")
        if web not in VALID_PROVIDERS:
            raise ValueError(
                f"WEB_PROVIDER must be one of {sorted(VALID_PROVIDERS)}, got {web!r}"
            )

        catalog = _get("CATALOG_PROVIDER", "mock")
        if catalog not in VALID_PROVIDERS:
            raise ValueError(
                f"CATALOG_PROVIDER must be one of {sorted(VALID_PROVIDERS)}, "
                f"got {catalog!r}"
            )

        knowledge = _get("KNOWLEDGE_PROVIDER", "mock")
        if knowledge not in VALID_PROVIDERS:
            raise ValueError(
                f"KNOWLEDGE_PROVIDER must be one of {sorted(VALID_PROVIDERS)}, "
                f"got {knowledge!r}"
            )

        return cls(
            app_profile=_get("APP_PROFILE", "tutorial"),
            tutorial_runtime=runtime,
            web_provider=web,
            catalog_provider=catalog,
            knowledge_provider=knowledge,
            model_name=_get("MODEL_NAME", "openai:gpt-4.1-mini"),
            model_base_url=_get("MODEL_BASE_URL") or None,
            model_api_key=_get("MODEL_API_KEY") or None,
            tavily_api_key=_get("TAVILY_API_KEY") or None,
            ragflow_base_url=_get("RAGFLOW_BASE_URL") or None,
            ragflow_api_key=_get("RAGFLOW_API_KEY") or None,
            mysql_host=_get("MYSQL_HOST", "127.0.0.1"),
            mysql_port=int(_get("MYSQL_PORT", "3307")),
            mysql_user=_get("MYSQL_USER", "tutorial_reader"),
            mysql_password=_get("MYSQL_PASSWORD", "tutorial_reader"),
            mysql_database=_get("MYSQL_DATABASE", "research_copilot"),
        )
