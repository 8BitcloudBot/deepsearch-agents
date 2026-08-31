#!/usr/bin/env python3
"""复盘最近 N 个回合：问题/回答摘要/证据来源分布/limitations/claims。

用法：uv run --extra dev python scripts/turns_review.py [N] [--db PATH]
默认 N=10，库 .data/conversations.sqlite3。
"""

from __future__ import annotations

import json
import sqlite3
import sys


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    db = ".data/conversations.sqlite3"
    if "--db" in sys.argv:
        db = sys.argv[sys.argv.index("--db") + 1]
    n = int(args[0]) if args else 10

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, question, status, answer, result_json, created_at, completed_at "
        "FROM turns ORDER BY created_at DESC LIMIT ?",
        (n,),
    ).fetchall()

    for row in reversed(rows):
        result = json.loads(row["result_json"]) if row["result_json"] else {}
        evidence = result.get("evidence", []) or []
        srcs = []
        for e in evidence:
            eid = str(e.get("evidence_id", ""))
            title = str(e.get("title", ""))
            if e.get("source_kind") == "web":
                srcs.append("web")
            elif "upload-" in eid or title.endswith(".md"):
                srcs.append("personal/shared-doc")
            else:
                srcs.append("main-library")
        print(f"=== {row['created_at'][:19]} [{row['status']}] {row['question'][:60]}")
        print(f"  回答({len(row['answer'] or '')}字): {(row['answer'] or '')[:160].replace(chr(10), ' | ')}")
        print(f"  claims={len(result.get('claims', []) or [])} limitations={len(result.get('limitations', []) or [])}")
        for item in (result.get("limitations", []) or [])[:4]:
            print(f"    L: {str(item)[:90]}")
        print(f"  证据来源: {srcs}")
        print()

if __name__ == "__main__":
    main()
