"""E2E: Full API closure over the real product WebSocket path.

Single sync TestClient lifecycle (shared portal): upload constraints.md
carrying a unique marker, join /ws/{thread_id} BEFORE the task starts,
start the task via POST /api/task, collect every task event exclusively
from the WebSocket, then verify the two generated reports and their
downloads. No event-bus access, no async test client.
"""

import uuid

from starlette.testclient import TestClient

from app.api.server import create_app
from app.settings import Phase2Settings

TERMINAL_TYPES = ("task_completed", "task_cancelled", "task_failed")
REQUIRED_TOOLS = ("internet_search", "list_sql_tables", "list_knowledge_assistants")


def test_full_api_closure_via_websocket(tmp_path, monkeypatch):
    # Isolate the file root (updated/ and output/ are cwd-relative) and
    # mint a fresh, valid thread UUID plus unique marker per run.
    monkeypatch.chdir(tmp_path)
    tid = str(uuid.uuid4())
    marker = f"UNIQUE-E2E-CONSTRAINT-{uuid.uuid4().hex}"

    with TestClient(create_app(settings=Phase2Settings())) as client:
        # 1. Upload constraints.md carrying the unique marker
        r = client.post(
            "/api/upload",
            data={"thread_id": tid},
            files={
                "files": (
                    "constraints.md",
                    f"# {marker}\n\nKeep it short.".encode(),
                    "text/markdown",
                )
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["files"][0]["name"] == "constraints.md"

        # 2. Join /ws/{thread_id} BEFORE the task starts. The server
        #    establishes its subscription before accepting, so no event
        #    emitted by POST /api/task can be missed.
        with client.websocket_connect(f"/ws/{tid}") as ws:
            r2 = client.post(
                "/api/task", json={"query": "research aspirin", "thread_id": tid}
            )
            assert r2.status_code == 202, r2.text

            # 3. Collect events only from the WebSocket until the
            #    terminal event arrives.
            collected: list[dict] = []
            while True:
                evt = ws.receive_json()
                collected.append(evt)
                if evt["type"] in TERMINAL_TYPES:
                    break

        # 4. All three provider families must appear as tool events
        tool_names = {e["data"].get("tool_name", "") for e in collected}
        for tool in REQUIRED_TOOLS:
            assert tool in tool_names, f"missing {tool}; got {sorted(tool_names)}"

        # 5. Exactly one terminal event, and it must be task_completed
        terminals = [e for e in collected if e["type"] in TERMINAL_TYPES]
        assert len(terminals) == 1, [e["type"] for e in terminals]
        assert terminals[0]["type"] == "task_completed"

        # 6. Both reports are listed
        r = client.get("/api/files", params={"thread_id": tid})
        assert r.status_code == 200, r.text
        fnames = {f["name"] for f in r.json()["files"]}
        assert "tutorial-report.md" in fnames
        assert "tutorial-report.pdf" in fnames

        # 7. Markdown contains the unique marker and all three provider modes
        r = client.get(
            "/api/download",
            params={"thread_id": tid, "path": "tutorial-report.md"},
        )
        assert r.status_code == 200, r.text
        md = r.text
        assert marker in md
        assert "web_mode" in md
        assert "catalog_mode" in md
        assert "knowledge_mode" in md

        # 8. PDF starts with the %PDF magic header
        r = client.get(
            "/api/download",
            params={"thread_id": tid, "path": "tutorial-report.pdf"},
        )
        assert r.status_code == 200, r.text
        assert r.content[:4] == b"%PDF"
