"""三场景真机回归：流式 / RAG / 时效题（最终配置组合）。

需 .env 提供真实 MODEL_API_KEY；用法：
    MODEL_STREAMED_SYNTHESIS=true uv run --extra dev python scripts/regression_e2e.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
for line in open(".env"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    os.environ.setdefault(key.strip(), value.strip())
os.environ["MODEL_STREAMED_SYNTHESIS"] = "true"

# 脚本性质：.env 装载先于 app import，E402 预期
from app.conversation.runtime import build_conversation_application  # noqa: E402

application = build_conversation_application(
    os.environ,
    runtime_root=Path(".").resolve(),
    store_path=Path(".data/smoke-regression.sqlite3"),
    report_root=Path(".data/smoke-regression-reports"),
)
user = application.store.authenticate("user", "0000")
print(
    "== 场景配置：",
    os.environ["MODEL_NAME"],
    "| streamed:",
    os.environ["MODEL_STREAMED_SYNTHESIS"],
)


async def run_turn(conv, question, use_web, label, assertions):
    turn = await application.submit(user, conv.id, question=question, use_web=use_web)
    events = []
    state = {"first": None, "count": 0}
    t0 = time.monotonic()

    def track(event):
        if event["type"] == "answer.delta" and event.get("data", {}).get("partial"):
            state["count"] += 1
            if state["first"] is None:
                state["first"] = time.monotonic() - t0
        events.append(event)

    final = await application.execute(user, conv.id, turn.id, emit=track)
    elapsed = time.monotonic() - t0
    result = final.result or {}
    partials = [
        e
        for e in events
        if e["type"] == "answer.delta" and e.get("data", {}).get("partial")
    ]
    finals = [
        e
        for e in events
        if e["type"] == "answer.delta" and not e.get("data", {}).get("partial")
    ]
    print(
        f"\n[{label}] status={final.status} 耗时={elapsed:.1f}s"
        f" 首字={state['first'] if state['first'] else '—'}s"
        f" partials={len(partials)} finals={len(finals)}"
        f" claims={len(result.get('claims', []))}"
        f" evidence={len(result.get('evidence', []))}"
        f" limitations={len(result.get('limitations', []))}"
    )
    print("  回答:", final.answer[:180].replace("\n", " "))
    ok = all(check(final, result, events) for check in assertions)
    print("  断言:", "PASS" if ok else "FAIL")
    return ok


async def main():
    results = []

    # ── 场景 1：流式（知识题）──
    conv1 = application.store.create_conversation(user, title="回归-流式")

    def check_stream(final, result, events):
        partials = [
            e
            for e in events
            if e["type"] == "answer.delta" and e.get("data", {}).get("partial")
        ]
        finals = [
            e
            for e in events
            if e["type"] == "answer.delta" and not e.get("data", {}).get("partial")
        ]
        assert final.status == "completed" and len(partials) > 5 and len(finals) == 1
        assert "[" in final.answer, "完成态应带引用编号"
        return True

    results.append(
        await run_turn(
            conv1,
            "LangGraph 的图状态是如何管理的？",
            False,
            "场景1 流式知识题",
            [check_stream],
        )
    )

    # ── 场景 2：RAG（私域文档入库→提问→引用）──
    handbook = Path("/tmp/company-handbook.md")
    if not handbook.exists():
        handbook.write_text(
            "# 星尘科技员工手册\n\n## 出差报销政策\n\n"
            '星尘科技实行"48 小时报销制"：出差返程后 48 小时内必须在'
            "OA 系统提交报销单。住宿标准为一线城市每天 600 元，"
            "非一线城市每天 450 元。\n",
            encoding="utf-8",
        )
    entry = application.upload_store.ingest_path(
        user.id, "company-handbook.md", handbook
    )
    print(f"\n[场景2 入库] {entry}")
    conv2 = application.store.create_conversation(user, title="回归-RAG")

    def check_rag(final, result, events):
        assert final.status == "completed"
        titles = [e.get("title") for e in result.get("evidence", [])]
        assert "company-handbook.md" in titles, f"证据应来自入库文档，实际 {titles}"
        assert "48 小时" in final.answer or "48小时" in final.answer, (
            "回答应包含入库事实"
        )
        return True

    results.append(
        await run_turn(
            conv2,
            "我们公司出差返程后多长时间内必须提交报销单？",
            False,
            "场景2 RAG 私域",
            [check_rag],
        )
    )

    # ── 场景 3：时效题（web）──
    conv3 = application.store.create_conversation(user, title="回归-时效")

    def check_timeliness(final, result, events):
        assert final.status == "completed"
        web = [e for e in result.get("evidence", []) if e.get("source_kind") == "web"]
        assert web, "时效题应有 web 证据"
        low = [e["score"] for e in web]
        assert any(s < 0.95 for s in low), f"web 证据应为绝对分而非全满分 {low}"
        return True

    results.append(
        await run_turn(
            conv3,
            "DeepSeek 官方 API 最近有什么新功能或模型更新？请给截至目前的最新情况。",
            True,
            "场景3 时效题",
            [check_timeliness],
        )
    )

    verdict = "全部 PASS" if all(results) else "存在 FAIL"
    print(f"\n=== 回归结论: {verdict}（{sum(results)}/{len(results)}）===")


asyncio.run(main())
