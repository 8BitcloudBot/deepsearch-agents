"""Phase 0 FastAPI application — health contract only."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns a minimal app with only the /health endpoint.
    No database connections, external providers, or agent logic in Phase 0.
    """
    app = FastAPI(title="research-copilot-api")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "research-copilot-api", "phase": "0"}

    return app
