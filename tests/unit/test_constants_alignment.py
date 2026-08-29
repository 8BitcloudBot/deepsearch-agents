"""双真源常量对齐锁定（H3）：同值常量散落两处时用断言防止漂移。"""

from app.api import server as server_module
from app.conversation import runtime as runtime_module
from app.knowledge import readers as readers_module
from app.providers import tavily as tavily_module


def test_library_file_size_matches_readers_limit() -> None:
    assert server_module._LIBRARY_MAX_FILE_SIZE == readers_module.MAX_FILE_SIZE_BYTES


def test_web_delivery_limit_matches_tavily_provider() -> None:
    assert runtime_module._MAX_WEB_HITS_PER_QUERY == tavily_module.MAX_DELIVERY_LIMIT


def test_cors_origins_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEARCH_CORS_ORIGINS", raising=False)
    default = server_module._cors_origins()
    assert "http://127.0.0.1:5181" in default

    monkeypatch.setenv("DEEPSEARCH_CORS_ORIGINS", "https://a.example, https://b.example")
    assert server_module._cors_origins() == ["https://a.example", "https://b.example"]


def test_cookie_secure_flag(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEARCH_COOKIE_SECURE", raising=False)
    assert server_module._cookie_secure() is False
    monkeypatch.setenv("DEEPSEARCH_COOKIE_SECURE", "true")
    assert server_module._cookie_secure() is True
