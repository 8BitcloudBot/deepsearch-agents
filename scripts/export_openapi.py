#!/usr/bin/env python3
"""导出 OpenAPI 合同（H18 防漂移基建）。

用法：uv run python scripts/export_openapi.py [输出路径，默认 docs/openapi.json]
前后端合同变更后重新导出，供对照与（可选）openapi-typescript 生成使用。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/openapi.json")
    from app.main import app

    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[openapi] exported {len(schema.get('paths', {}))} paths -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
