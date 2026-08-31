"""合同防漂移（H18）：OpenAPI schema 与响应模型的关键形状锁定。"""

from app.main import app


def _schema() -> dict:
    return app.openapi()


def test_lite_endpoint_excludes_turns_and_attachments() -> None:
    schema = _schema()
    summary = schema["components"]["schemas"]["ConversationSummary"]
    assert set(summary["properties"]) == {
        "id",
        "title",
        "owner_id",
        "created_at",
        "updated_at",
    }


def test_full_conversation_response_keeps_legacy_fields() -> None:
    schema = _schema()
    response = schema["components"]["schemas"]["ConversationResponse"]
    # 向后兼容：完整端点合同不得移除既有字段
    assert {"turns", "attachments"} <= set(response["properties"])
