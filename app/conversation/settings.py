"""Environment configuration for the schema 5.0 conversation product."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath


def _optional(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key, "").strip()
    return value or None


def _positive_float(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        value = float(env.get(key, str(default)))
    except ValueError as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def _unit_interval_optional(env: Mapping[str, str], key: str) -> float | None:
    raw = env.get(key, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be numeric") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{key} must be between 0 and 1")
    return value


def _non_negative_int(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        value = int(env.get(key, str(default)))
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{key} must not be negative")
    return value


def _minimum_score(env: Mapping[str, str]) -> float:
    try:
        value = float(env.get("KNOWLEDGE_MIN_SCORE", "0.40"))
    except ValueError as exc:
        raise ValueError("KNOWLEDGE_MIN_SCORE must be numeric") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError("KNOWLEDGE_MIN_SCORE must be between 0 and 1")
    return value


def _safe_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized.strip()
        or path.is_absolute()
        or ".." in path.parts
        or normalized.startswith("~")
    ):
        raise ValueError("knowledge index path must be a safe relative path")
    return str(path)


@dataclass(frozen=True)
class KnowledgeSettings:
    index_path: str = ".data/knowledge-index-beginner-v2"
    collection: str = "deepsearch-beginner-v2"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    min_score: float = 0.40


@dataclass(frozen=True)
class ConversationSettings:
    model_name: str = "openai:gpt-4.1-mini"
    model_base_url: str | None = None
    model_api_key: str | None = None
    tavily_api_key: str | None = None
    model_timeout_seconds: float = 60.0
    model_temperature: float | None = 0.2
    model_top_p: float | None = None
    model_max_retries: int = 2
    knowledge: KnowledgeSettings = KnowledgeSettings()

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> ConversationSettings:
        model_name = environ.get("MODEL_NAME", cls.model_name).strip()
        if not model_name:
            raise ValueError("MODEL_NAME must not be empty")
        return cls(
            model_name=model_name,
            model_base_url=_optional(environ, "MODEL_BASE_URL"),
            model_api_key=_optional(environ, "MODEL_API_KEY"),
            tavily_api_key=_optional(environ, "TAVILY_API_KEY"),
            model_timeout_seconds=_positive_float(
                environ, "MODEL_TIMEOUT_SECONDS", cls.model_timeout_seconds
            ),
            model_temperature=(
                _unit_interval_optional(environ, "MODEL_TEMPERATURE")
                if environ.get("MODEL_TEMPERATURE", "").strip()
                else cls.model_temperature
            ),
            model_top_p=_unit_interval_optional(environ, "MODEL_TOP_P"),
            model_max_retries=_non_negative_int(
                environ, "MODEL_MAX_RETRIES", cls.model_max_retries
            ),
            knowledge=KnowledgeSettings(
                index_path=_safe_relative_path(
                    environ.get(
                        "KNOWLEDGE_INDEX_PATH",
                        ".data/knowledge-index-beginner-v2",
                    )
                ),
                collection=environ.get(
                    "KNOWLEDGE_COLLECTION", "deepsearch-beginner-v2"
                ).strip(),
                embedding_model=environ.get(
                    "KNOWLEDGE_EMBEDDING_MODEL",
                    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                ).strip(),
                min_score=_minimum_score(environ),
            ),
        )
