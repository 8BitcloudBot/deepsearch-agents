from pathlib import Path

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.server import create_app
from app.conversation.application import ConversationApplication
from app.conversation.contracts import Claim, EvidenceItem, TurnResult
from app.conversation.report import ConversationReport
from app.conversation.store import ConversationStore


class NoopApplication:
    def __init__(self, store: ConversationStore, report: ConversationReport):
        self.store = store
        self.report = report
        self.capabilities = {
            "model": {"status": "unavailable"},
            "knowledge": {"status": "ready"},
            "web": {"status": "unavailable"},
            "session_file": {"status": "unavailable"},
        }

    async def submit(self, user, conversation_id, *, question, use_web):
        return self.store.start_turn(
            user, conversation_id, question=question, use_web=use_web
        )

    async def execute(self, user, conversation_id, turn_id, *, emit=None):
        return self.store.get_turn(user, conversation_id, turn_id)


def client(tmp_path: Path) -> TestClient:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    report = ConversationReport(tmp_path / "reports", store)
    return TestClient(
        create_app(
            store=store,
            conversation_application=NoopApplication(store, report),
        )
    )


def login(client: TestClient, username: str = "user") -> None:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": "0000"}
    )
    assert response.status_code == 200


def test_login_and_conversation_contract(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        assert http.get("/api/conversations").status_code == 401
        login(http)

        created = http.post("/api/conversations", json={"title": "我的研究"})
        assert created.status_code == 201
        conversation = created.json()
        assert conversation["title"] == "我的研究"
        assert conversation["turns"] == []

        listed = http.get("/api/conversations")
        assert [item["id"] for item in listed.json()] == [conversation["id"]]


def test_health_uses_runtime_capability_snapshot(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        response = http.get("/health")

    assert response.status_code == 200
    assert response.json()["schema_version"] == "5.0.0"
    assert response.json()["capabilities"] == {
        "model": {"status": "unavailable"},
        "knowledge": {"status": "ready"},
        "web": {"status": "unavailable"},
        "session_file": {"status": "unavailable"},
    }


def test_turn_submission_accepts_web_toggle_and_only_markdown_download(
    tmp_path: Path,
) -> None:
    with client(tmp_path) as http:
        login(http)
        conversation = http.post("/api/conversations", json={}).json()
        response = http.post(
            f"/api/conversations/{conversation['id']}/turns",
            json={"question": "如何入门？", "use_web": False},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "started"
        assert response.json()["use_web"] is False

        assert (
            http.get(f"/api/conversations/{conversation['id']}/report").status_code
            == 404
        )
        assert (
            http.get(
                f"/api/conversations/{conversation['id']}/artifacts/research-citations.json"
            ).status_code
            == 404
        )
        assert (
            http.get(
                f"/api/conversations/{conversation['id']}/artifacts/research-report.pdf"
            ).status_code
            == 404
        )


def test_report_download_regenerates_completed_turns_from_sqlite(
    tmp_path: Path,
) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")
    report = ConversationReport(tmp_path / "reports", store)
    application = NoopApplication(store, report)
    user = store.authenticate("user", "0000")
    assert user is not None
    conversation = store.create_conversation(user, "旧报告")
    turn = store.start_turn(
        user, conversation.id, question="什么是状态？", use_web=False
    )
    item = EvidenceItem(
        evidence_id="ev-knowledge-1",
        source_kind="knowledge",
        title="状态文档",
        locator_kind="chunk",
        locator_value="guide#state",
        quote="状态用于保存回合上下文。",
    )
    store.complete_turn(
        user,
        conversation.id,
        turn.id,
        TurnResult(
            schema_version="5.0.0",
            answer="状态用于保存上下文。[1]",
            claims=(Claim("claim-1", "状态保存上下文。", (item.evidence_id,)),),
            evidence=(item,),
            limitations=(),
        ),
    )
    stale = tmp_path / "reports" / conversation.id / "research-report.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("旧格式报告", encoding="utf-8")
    store.record_report(user, conversation.id, path=str(stale), checksum="stale")

    with TestClient(
        create_app(
            store=store,
            conversation_application=application,
        )
    ) as http:
        login(http)
        response = http.get(f"/api/conversations/{conversation.id}/report")

    assert response.status_code == 200
    assert "旧格式报告" not in response.text
    assert "## 证据附录（累计来源索引）" in response.text



def test_user_cannot_access_admin_conversation(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        login(http, "admin")
        admin_conversation = http.post(
            "/api/conversations", json={"title": "管理研究"}
        ).json()
        http.post("/api/auth/logout")
        login(http, "user")

        response = http.get(f"/api/conversations/{admin_conversation['id']}")
        assert response.status_code == 404


def test_admin_can_list_and_remove_user_data(tmp_path: Path) -> None:
    with client(tmp_path) as http:
        login(http, "user")
        user_conversation = http.post(
            "/api/conversations", json={"title": "待清理"}
        ).json()
        http.post("/api/auth/logout")
        login(http, "admin")

        listed = http.get("/api/admin/users")
        assert listed.status_code == 200
        user = next(item for item in listed.json() if item["username"] == "user")
        assert user["conversation_count"] == 1

        removed = http.delete(f"/api/admin/users/{user['id']}/data")
        assert removed.status_code == 204
        assert (
            http.get(f"/api/conversations/{user_conversation['id']}").status_code == 404
        )


def test_websocket_requires_authentication(tmp_path: Path) -> None:
    repository = ConversationStore(tmp_path / "reasonix.sqlite3")
    user = repository.authenticate("user", "0000")
    assert user is not None
    conversation = repository.create_conversation(user, "未登录")
    with client(tmp_path) as http:
        with pytest.raises(WebSocketDisconnect) as error:
            with http.websocket_connect(f"/api/conversations/{conversation.id}/events"):
                pass
        assert error.value.code == 4401


def test_websocket_success_has_one_terminal_event_and_aggregated_stages(
    tmp_path: Path,
) -> None:
    store = ConversationStore(tmp_path / "reasonix.sqlite3")

    class Engine:
        async def run(self, turn, *, user_knowledge=None):
            item = EvidenceItem(
                evidence_id="ev-knowledge-1",
                source_kind="knowledge",
                title="知识",
                locator_kind="chunk",
                locator_value="guide.md#intro",
                quote="证据",
            )
            return TurnResult(
                schema_version="5.0.0",
                answer="回答。[1]",
                claims=(Claim("claim-1", "结论", (item.evidence_id,)),),
                evidence=(item,),
                limitations=(),
            )


    application = ConversationApplication(
        store, Engine(), ConversationReport(tmp_path / "reports", store)
    )
    http = TestClient(
        create_app(
            store=store,
            conversation_application=application,
        )
    )
    with http:
        login(http)
        conversation = http.post("/api/conversations", json={}).json()
        with http.websocket_connect(
            f"/api/conversations/{conversation['id']}/events"
        ) as socket:
            started = http.post(
                f"/api/conversations/{conversation['id']}/turns",
                json={"question": "问题", "use_web": False},
            )
            assert started.status_code == 202
            events = []
            while True:
                event = socket.receive_json()
                events.append(event)
                if event["type"] in {"turn.completed", "turn.failed"}:
                    break

    assert events[0]["type"] == "turn.started"
    assert "web" not in {event.get("stage") for event in events}
    assert [event["type"] for event in events].count("turn.completed") == 1
    assert [event["type"] for event in events].count("turn.failed") == 0
