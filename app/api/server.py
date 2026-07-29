"""FastAPI application factory with HTTP routes and WebSocket.

Implements the locked Phase 2 contract:
POST /api/task, POST /api/task/{thread_id}/cancel,
POST /api/upload, GET /api/files, GET /api/download,
WS /ws/{thread_id}, GET /health → phase: "2".
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.agent.runtime import TutorialRuntime
from app.api.events import InMemoryEventBus
from app.api.schemas import (
    FileInfo,
    FileListResponse,
    HeartbeatMessage,
    TaskCancelResponse,
    TaskStartRequest,
    TaskStartResponse,
    UploadResponse,
)
from app.api.tasks import TaskRegistry
from app.providers.contracts import ProviderBundle
from app.settings import Phase2Settings
from app.tools.files import (
    MAX_FILE_SIZE_BYTES,
    SessionWorkspace,
    save_uploaded_file,
)


def create_app(
    settings: Phase2Settings | None = None,
    bundle: ProviderBundle | None = None,
    runtime: TutorialRuntime | None = None,
    events: InMemoryEventBus | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application for Phase 2.

    Accepts optional overrides for testing. In production, settings
    drive the construction of bundle, runtime, and events.
    """
    app = FastAPI(title="research-copilot-api")

    settings = settings or Phase2Settings.from_env()
    events = events or InMemoryEventBus()
    registry: TaskRegistry | None = None

    if runtime is not None:
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="updated",
            base_output="output",
        )
    elif bundle is not None and runtime is not None:
        registry = TaskRegistry(
            runtime=runtime,
            events=events,
            base_upload="updated",
            base_output="output",
        )

    # Workaround: always create a registry for /health and /upload
    # In production, this is wired via build_providers + create_tutorial_agent
    if registry is None:
        from app.agent.runtime import MockTutorialRuntime

        if bundle is None:
            from app.providers.mock import (
                MockCatalogProvider,
                MockKnowledgeProvider,
                MockWebProvider,
            )

            bundle = ProviderBundle(
                web=MockWebProvider(),
                catalog=MockCatalogProvider(),
                knowledge=MockKnowledgeProvider(),
                web_mode="mock",
                catalog_mode="mock",
                knowledge_mode="mock",
            )
        default_rt = MockTutorialRuntime(bundle, events)
        registry = TaskRegistry(
            runtime=default_rt,
            events=events,
            base_upload="updated",
            base_output="output",
        )

    app.state.events = events
    app.state.registry = registry

    # ── Health ────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        web_mode = getattr(bundle, "web_mode", "mock") if bundle else "mock"
        catalog_mode = getattr(bundle, "catalog_mode", "mock") if bundle else "mock"
        knowledge_mode = getattr(bundle, "knowledge_mode", "mock") if bundle else "mock"
        return {
            "status": "ok",
            "service": "research-copilot-api",
            "phase": "2",
            "tutorial_profile": "tutorial",
            "tutorial_runtime": settings.tutorial_runtime,
            "web_provider": web_mode,
            "catalog_provider": catalog_mode,
            "knowledge_provider": knowledge_mode,
        }

    # ── Task ──────────────────────────────────────────────────────────────

    @app.post("/api/task", status_code=202)
    async def start_task(body: TaskStartRequest):
        try:
            tid = registry.start(body.query)
            return TaskStartResponse(thread_id=tid)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/api/task/{thread_id}/cancel")
    async def cancel_task(thread_id: str):
        status = await registry.cancel(thread_id)
        if status == "not_found":
            raise HTTPException(status_code=404, detail="task not found")
        return TaskCancelResponse(thread_id=thread_id, status=status)

    # ── Upload ────────────────────────────────────────────────────────────

    @app.post("/api/upload")
    async def upload_file(file: UploadFile = File(...)):
        if not file.filename:
            raise HTTPException(status_code=400, detail="empty filename")
        data = await file.read()
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="file too large")
        # Use a temporary workspace to save the file
        import uuid as _uuid

        tid = str(_uuid.uuid4())
        ws = SessionWorkspace.for_thread(
            thread_id=tid,
            base_upload="updated",
            base_output="output",
        )
        try:
            saved = save_uploaded_file(ws, file.filename, data)
            return UploadResponse(filename=file.filename, size=saved.stat().st_size)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    # ── Files ─────────────────────────────────────────────────────────────

    @app.get("/api/files")
    async def list_files(thread_id: str = Query(...)):
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload="updated",
            base_output="output",
        )
        output_dir = ws.output_dir
        if not output_dir.exists():
            return FileListResponse(files=[])

        files = []
        for fpath in sorted(output_dir.iterdir()):
            if fpath.is_file():
                files.append(
                    FileInfo(
                        name=fpath.name,
                        path=fpath.name,
                        size=fpath.stat().st_size,
                        media_type=_guess_media_type(fpath.name),
                    )
                )
        return FileListResponse(files=files)

    @app.get("/api/download")
    async def download_file(thread_id: str = Query(...), path: str = Query(...)):
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload="updated",
            base_output="output",
        )
        try:
            resolved = ws.resolve_output(path)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid path")
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail="file not found")
        media_type = _guess_media_type(path)
        return FileResponse(
            str(resolved),
            media_type=media_type,
            filename=resolved.name,
        )

    # ── WebSocket ─────────────────────────────────────────────────────────

    @app.websocket("/ws/{thread_id}")
    async def websocket_endpoint(ws: WebSocket, thread_id: str):
        await ws.accept()

        async with events.subscribe(thread_id) as subscription:
            # Race between queue.get(), overflowed, and client messages
            async def _send_events():
                while True:
                    get_task = asyncio.create_task(subscription.queue.get())
                    overflow_task = asyncio.create_task(subscription.overflowed.wait())
                    done, _ = await asyncio.wait(
                        [get_task, overflow_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if get_task in done:
                        event = get_task.result()
                        if ws.client_state != WebSocketState.CONNECTED:
                            return
                        try:
                            await ws.send_text(event.model_dump_json())
                        except Exception:
                            return
                    if overflow_task in done:
                        if ws.client_state == WebSocketState.CONNECTED:
                            await ws.close(code=1013)
                        return
                    # Cancel unfinished tasks
                    for t in [get_task, overflow_task]:
                        if not t.done():
                            t.cancel()

            # Client message handler
            async def _recv_messages():
                while True:
                    try:
                        data = await ws.receive_text()
                        msg = json.loads(data)
                        if msg.get("type") == "ping":
                            await ws.send_text(HeartbeatMessage().model_dump_json())
                    except (WebSocketDisconnect, Exception):
                        return

            # Run both concurrently
            send_task = asyncio.create_task(_send_events())
            recv_task = asyncio.create_task(_recv_messages())
            done, _ = await asyncio.wait(
                [send_task, recv_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in [send_task, recv_task]:
                if not t.done():
                    t.cancel()

    return app


def _guess_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    return mapping.get(ext, "application/octet-stream")
