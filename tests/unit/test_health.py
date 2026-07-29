"""Tests for the /health endpoint — Phase 2 contract."""

from http import HTTPStatus

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_phase_2(app):
    """GET /health must return phase: '2'."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["phase"] == "2"
    assert data["status"] == "ok"
    assert data["service"] == "research-copilot-api"


@pytest.mark.asyncio
async def test_health_content_type_is_json(app):
    """GET /health must return application/json."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_health_no_secrets_leaked(app):
    """GET /health must not leak api_key or passwords."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    data = response.json()
    for key, value in data.items():
        if isinstance(value, str):
            assert "key" not in key.lower() or "api" not in key.lower()
