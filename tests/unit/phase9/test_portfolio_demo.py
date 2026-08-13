from __future__ import annotations

import os

import pytest


class EmptyKnowledgeRetriever:
    def search(self, _query: str, *, limit: int = 8, **_kwargs):
        assert limit == 8
        return ()


def test_demo_factory_does_not_read_provider_credentials(monkeypatch):
    from examples.portfolio_demo.app import create_demo_app

    protected = {
        "MODEL_API_KEY",
        "TAVILY_API_KEY",
        "MYSQL_PASSWORD",
        "PHASE45_REAL_SHOWCASE_SMOKE",
    }
    original_get = os.environ.get

    def guarded_get(key, default=None):
        if key in protected:
            raise AssertionError(f"demo read protected environment key {key}")
        return original_get(key, default)

    monkeypatch.setattr(os.environ, "get", guarded_get)

    app = create_demo_app("success")

    assert app.title == "research-copilot-api"
    assert app.state.portfolio_demo_scenario == "success"


@pytest.mark.parametrize(
    "scenario", ["success", "degraded", "failure", "formal-knowledge"]
)
def test_demo_factory_accepts_documented_scenarios(scenario):
    from examples.portfolio_demo.app import create_demo_app

    knowledge = EmptyKnowledgeRetriever() if scenario == "formal-knowledge" else None
    app = create_demo_app(scenario, knowledge_retriever=knowledge)

    assert app.state.portfolio_demo_scenario == scenario


def test_demo_factory_rejects_unknown_scenario():
    from examples.portfolio_demo.app import create_demo_app

    with pytest.raises(ValueError, match="scenario must be one of"):
        create_demo_app("live")


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_demo_cli_accepts_loopback_hosts(host):
    from scripts.portfolio_demo import validate_server_address

    assert validate_server_address(host, 8000) == (host, 8000)


@pytest.mark.parametrize(
    ("host", "port", "message"),
    [
        ("0.0.0.0", 8000, "loopback"),
        ("192.0.2.10", 8000, "loopback"),
        ("127.0.0.1", 0, "between 1 and 65535"),
        ("127.0.0.1", 65536, "between 1 and 65535"),
    ],
)
def test_demo_cli_rejects_unsafe_server_addresses(host, port, message):
    from scripts.portfolio_demo import validate_server_address

    with pytest.raises(ValueError, match=message):
        validate_server_address(host, port)
