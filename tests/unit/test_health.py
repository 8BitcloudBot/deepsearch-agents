"""Tests for the /health endpoint — Phase 0 contract."""

from http import HTTPStatus

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_returns_exact_contract(app):
    """GET /health must return the exact Phase 0 JSON contract."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data == {
        "status": "ok",
        "service": "research-copilot-api",
        "phase": "0",
    }


@pytest.mark.asyncio
async def test_health_content_type_is_json(app):
    """GET /health must return application/json."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_health_no_unexpected_keys(app):
    """GET /health must not leak extra fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    data = response.json()
    allowed_keys = {"status", "service", "phase"}
    assert set(data.keys()) == allowed_keys
