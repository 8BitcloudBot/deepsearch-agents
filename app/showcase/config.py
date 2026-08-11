"""Lazy, fail-closed configuration for the explicit showcase runtime."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from app.knowledge.contracts import resolve_knowledge_index_path
from app.showcase.contracts import (
    Limitation,
    ShowcaseCapabilities,
    SourceKind,
    resolve_capabilities,
)


@dataclass(frozen=True)
class ShowcaseRuntimeConfig:
    capabilities: ShowcaseCapabilities
    model_name: str = "openai:gpt-4.1-mini"
    model_base_url: str | None = None
    model_api_key: str | None = field(default=None, repr=False)
    web_provider: str | None = None
    tavily_api_key: str | None = field(default=None, repr=False)
    catalog_provider: str | None = None
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_user: str | None = None
    mysql_password: str | None = field(default=None, repr=False)
    mysql_database: str | None = None
    knowledge_provider: str | None = None
    knowledge_index_path: str | None = None
    knowledge_collection: str | None = None
    knowledge_embedding_provider: str | None = None
    knowledge_embedding_model: str | None = None
    knowledge_embedding_version: str | None = None
    knowledge_embedding_dimension: int | None = None
    limitations: tuple[Limitation, ...] = ()

    @property
    def model_available(self) -> bool:
        return bool(self.model_name.strip() and self.model_api_key)

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> ShowcaseRuntimeConfig:
        capabilities = resolve_capabilities(environ)
        limitations = list(capabilities.limitations())
        if not capabilities.enabled:
            return cls(capabilities=capabilities, limitations=tuple(limitations))

        model_name = environ.get("MODEL_NAME", "openai:gpt-4.1-mini").strip()
        model_base_url = environ.get("MODEL_BASE_URL") or None
        model_api_key = environ.get("MODEL_API_KEY") or None
        if not model_name or not model_api_key:
            limitations.append(
                Limitation(
                    code="model-unavailable",
                    source_kind=None,
                    message="showcase model configuration is unavailable",
                )
            )
            return cls(
                capabilities=capabilities,
                model_name=model_name,
                model_base_url=model_base_url,
                limitations=tuple(limitations),
            )

        values: dict[str, object] = {
            "capabilities": capabilities,
            "model_name": model_name,
            "model_base_url": model_base_url,
            "model_api_key": model_api_key,
        }

        if capabilities.check(SourceKind.WEB).enabled:
            provider = environ.get("WEB_PROVIDER", "mock")
            values["web_provider"] = provider
            if provider != "tavily":
                limitations.append(
                    _source_limitation(
                        "provider-not-live",
                        SourceKind.WEB,
                        "web source requires the Tavily provider",
                    )
                )
            else:
                tavily_api_key = environ.get("TAVILY_API_KEY") or None
                values["tavily_api_key"] = tavily_api_key
                if not tavily_api_key:
                    limitations.append(
                        _source_limitation(
                            "configuration-missing",
                            SourceKind.WEB,
                            "web source configuration is incomplete",
                        )
                    )

        if capabilities.check(SourceKind.MYSQL).enabled:
            provider = environ.get("CATALOG_PROVIDER", "mock")
            values["catalog_provider"] = provider
            if provider != "mysql":
                limitations.append(
                    _source_limitation(
                        "provider-not-live",
                        SourceKind.MYSQL,
                        "catalog source requires the MySQL provider",
                    )
                )
            else:
                _read_mysql(environ, values, limitations)

        if capabilities.check(SourceKind.KNOWLEDGE).enabled:
            provider = environ.get("KNOWLEDGE_PROVIDER", "qdrant-local")
            values["knowledge_provider"] = provider
            if provider != "qdrant-local":
                limitations.append(
                    _source_limitation(
                        "provider-not-live",
                        SourceKind.KNOWLEDGE,
                        "knowledge source requires the qdrant-local provider",
                    )
                )
            else:
                index_path = environ.get(
                    "KNOWLEDGE_INDEX_PATH", ".data/knowledge-index"
                )
                collection = environ.get(
                    "KNOWLEDGE_COLLECTION", "deepsearch-showcase-v1"
                )
                embedding_provider = environ.get(
                    "KNOWLEDGE_EMBEDDING_PROVIDER", "fastembed"
                )
                embedding_model = environ.get(
                    "KNOWLEDGE_EMBEDDING_MODEL",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                )
                values.update(
                    knowledge_index_path=index_path,
                    knowledge_collection=collection,
                    knowledge_embedding_provider=embedding_provider,
                    knowledge_embedding_model=embedding_model,
                    knowledge_embedding_version="0.8.0",
                    knowledge_embedding_dimension=384,
                )
                try:
                    resolve_knowledge_index_path(index_path, runtime_root=Path.cwd())
                except ValueError:
                    limitations.append(
                        _source_limitation(
                            "configuration-invalid",
                            SourceKind.KNOWLEDGE,
                            "knowledge index path is invalid",
                        )
                    )
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", collection):
                    limitations.append(
                        _source_limitation(
                            "configuration-invalid",
                            SourceKind.KNOWLEDGE,
                            "knowledge collection is invalid",
                        )
                    )
                if (
                    embedding_provider != "fastembed"
                    or embedding_model
                    != "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                ):
                    limitations.append(
                        _source_limitation(
                            "configuration-invalid",
                            SourceKind.KNOWLEDGE,
                            "knowledge embedding configuration is unsupported",
                        )
                    )

        values["limitations"] = tuple(limitations)
        return cls(**values)


def _source_limitation(code: str, kind: SourceKind, message: str) -> Limitation:
    return Limitation(code=code, source_kind=kind, message=message)


def _read_mysql(
    environ: Mapping[str, str],
    values: dict[str, object],
    limitations: list[Limitation],
) -> None:
    values["mysql_host"] = environ.get("MYSQL_HOST", "127.0.0.1")
    values["mysql_user"] = environ.get("MYSQL_USER", "tutorial_reader")
    values["mysql_password"] = environ.get("MYSQL_PASSWORD") or None
    values["mysql_database"] = environ.get("MYSQL_DATABASE", "research_copilot")
    try:
        port = int(environ.get("MYSQL_PORT", "3307"))
        if not 1 <= port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        port = None
        limitations.append(
            _source_limitation(
                "configuration-invalid",
                SourceKind.MYSQL,
                "catalog source port is invalid",
            )
        )
    values["mysql_port"] = port

    if values["mysql_user"] != "tutorial_reader":
        limitations.append(
            _source_limitation(
                "configuration-invalid",
                SourceKind.MYSQL,
                "catalog source requires the approved read-only user",
            )
        )
    if not values["mysql_password"]:
        limitations.append(
            _source_limitation(
                "configuration-missing",
                SourceKind.MYSQL,
                "catalog source configuration is incomplete",
            )
        )

    host = values["mysql_host"]
    database = values["mysql_database"]
    if (
        not isinstance(host, str)
        or not host.strip()
        or any(char.isspace() for char in host)
    ):
        limitations.append(
            _source_limitation(
                "configuration-invalid",
                SourceKind.MYSQL,
                "catalog source host is invalid",
            )
        )
    if not isinstance(database, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]{0,63}", database
    ):
        limitations.append(
            _source_limitation(
                "configuration-invalid",
                SourceKind.MYSQL,
                "catalog source database is invalid",
            )
        )
