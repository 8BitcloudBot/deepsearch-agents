#!/usr/bin/env python3
"""Check local prerequisites for the conversation product."""

import argparse
import sys
from pathlib import Path

# 代码真实消费的配置键（settings.py + os.getenv 直读）
KNOWN_CONSUMED_KEYS = {
    "MODEL_NAME",
    "MODEL_NAME_LIGHT",
    "MODEL_BASE_URL",
    "MODEL_API_KEY",
    "MODEL_TIMEOUT_SECONDS",
    "MODEL_TEMPERATURE",
    "MODEL_TEMPERATURE_PLANNER",
    "MODEL_TEMPERATURE_SYNTHESIZER",
    "MODEL_TEMPERATURE_REVIEWER",
    "MODEL_TOP_P",
    "MODEL_MAX_RETRIES",
    "MODEL_STRUCTURED_OUTPUT",
    "MODEL_STREAMED_SYNTHESIS",
    "ENABLE_CITATION_VALIDATION",
    "CITATIONS_CHINESE_TOKENIZER",
    "TURN_STALE_SECONDS",
    "MAX_TURNS_PER_CONVERSATION",
    "HISTORY_TOKEN_BUDGET",
    "TAVILY_API_KEY",
    "KNOWLEDGE_INDEX_PATH",
    "KNOWLEDGE_COLLECTION",
    "KNOWLEDGE_EMBEDDING_MODEL",
    "KNOWLEDGE_EMBEDDING_VERSION",
    "KNOWLEDGE_EMBEDDING_DIMENSION",
    "KNOWLEDGE_MIN_SCORE",
    "DEEPSEARCH_SQLITE",
    "DEEPSEARCH_REPORT_ROOT",
    "DEEPSEARCH_TRACE",
    "DEEPSEARCH_CORS_ORIGINS",
    "DEEPSEARCH_COOKIE_SECURE",
}
# 历史遗留、当前代码零消费的键：出现在 .env 只提示不报错
KNOWN_UNUSED_PREFIXES = ("MYSQL_",)
KNOWN_UNUSED_KEYS = {"WEB_PROVIDER", "CATALOG_PROVIDER"}


def check_offline() -> int:
    """Check prerequisites that do not contact external providers."""
    print("[doctor] Running offline checks ...")
    version = sys.version_info
    if version.major != 3 or version.minor < 12:
        print(
            f"  [FAIL] Need Python 3.12+, got {version.major}.{version.minor}",
            file=sys.stderr,
        )
        print("[doctor] Offline checks failed.", file=sys.stderr)
        return 1
    print(f"  [OK] Python {version.major}.{version.minor}.{version.micro}")
    _check_env_keys(Path.cwd() / ".env")
    print("[doctor] All offline checks passed.")
    return 0


def _check_env_keys(env_path: Path) -> None:
    """对账 .env 键与代码消费清单：未知键告警（可能拼错）、遗留键提示。"""
    if not env_path.is_file():
        return
    keys: set[str] = set()
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.add(stripped.split("=", 1)[0].strip())
    unknown = sorted(
        key
        for key in keys
        if key not in KNOWN_CONSUMED_KEYS
        and key not in KNOWN_UNUSED_KEYS
        and not key.startswith(KNOWN_UNUSED_PREFIXES)
    )
    for key in unknown:
        print(f"  [WARN] .env 键 {key} 未被代码消费（检查拼写或移除）")
    unused = sorted(
        key
        for key in keys
        if key in KNOWN_UNUSED_KEYS or key.startswith(KNOWN_UNUSED_PREFIXES)
    )
    for key in unused:
        print(f"  [INFO] .env 键 {key} 当前代码零消费（历史遗留，可保留）")


def main() -> int:
    parser = argparse.ArgumentParser(description="Conversation product doctor")
    parser.add_argument(
        "--offline", action="store_true", help="Run local prerequisite checks"
    )
    args = parser.parse_args()
    if not args.offline:
        parser.error("--offline is required")
    return check_offline()


if __name__ == "__main__":
    sys.exit(main())
