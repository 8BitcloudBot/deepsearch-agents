"""FastAPI application factory with HTTP routes and WebSocket."""

import asyncio
import json
from pathlib import Path

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.agent.runtime import TutorialRuntime
from app.api.events import InMemoryEventBus
from app.api.schemas import (
    UUID_RE,
    CitationsResponse,
    FileInfo,
    FileListResponse,
    HeartbeatMessage,
    TaskCancelResponse,
    TaskStartRequest,
    TaskStartResponse,
    UploadFileInfo,
    UploadResponse,
)
from app.api.tasks import DuplicateTaskError, TaskRegistry
from app.providers.contracts import ProviderBundle
from app.settings import Phase2Settings
from app.tools.files import (
    MAX_FILE_SIZE_BYTES,
    SessionWorkspace,
    save_uploaded_file,
)


def _validate_uuid(tid: str, label: str = "thread_id") -> None:
    if not UUID_RE.fullmatch(tid):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}: must be a UUID, got {tid!r}",
        )


def create_app(
    settings: Phase2Settings | None = None,
    bundle: ProviderBundle | None = None,
    runtime: TutorialRuntime | None = None,
    events: InMemoryEventBus | None = None,
) -> FastAPI:
    app = FastAPI(title="research-copilot-api")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    settings = settings or Phase2Settings.from_env()
    events = events or InMemoryEventBus()

    if runtime is None:
        if settings.app_profile == "agent-research":
            from app.research.runtime import AgentResearchRuntime

            runtime = AgentResearchRuntime(events)
        else:
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
            runtime = MockTutorialRuntime(bundle, events)

    registry = TaskRegistry(
        runtime=runtime,
        events=events,
        base_upload="updated",
        base_output="output",
    )

    # ── Health ────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        wm = getattr(bundle, "web_mode", "mock") if bundle else "mock"
        cm = getattr(bundle, "catalog_mode", "mock") if bundle else "mock"
        km = getattr(bundle, "knowledge_mode", "mock") if bundle else "mock"
        return {
            "status": "ok",
            "service": "research-copilot-api",
            "phase": "2",
            "tutorial_profile": "tutorial",
            "tutorial_runtime": settings.tutorial_runtime,
            "app_profile": settings.app_profile,
            "web_provider": wm,
            "catalog_provider": cm,
            "knowledge_provider": km,
        }

    # ── Task ──────────────────────────────────────────────────────────────

    @app.post("/api/task", status_code=202)
    async def start_task(body: TaskStartRequest):
        try:
            tid = registry.start(body.query, thread_id=body.thread_id)
            return TaskStartResponse(thread_id=tid)
        except DuplicateTaskError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    @app.post("/api/task/{thread_id}/cancel")
    async def cancel_task(thread_id: str):
        _validate_uuid(thread_id)
        status = await registry.cancel(thread_id)
        if status == "not_found":
            raise HTTPException(status_code=404, detail="task not found")
        return TaskCancelResponse(thread_id=thread_id, status=status)

    # ── Upload ────────────────────────────────────────────────────────────

    @app.post("/api/upload")
    async def upload_file(
        thread_id: str = Form(...),
        files: list[UploadFile] = File(...),
    ):
        _validate_uuid(thread_id)
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload="updated",
            base_output="output",
        )
        results: list[UploadFileInfo] = []
        for f in files:
            if not f.filename:
                raise HTTPException(status_code=400, detail="empty filename")
            # Stream chunks with size limit
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = await f.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="file too large")
                chunks.append(chunk)
            data = b"".join(chunks)
            try:
                save_uploaded_file(ws, f.filename, data)
                results.append(UploadFileInfo(name=f.filename, size=len(data)))
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        return UploadResponse(thread_id=thread_id, files=results)

    # ── Files ─────────────────────────────────────────────────────────────

    @app.get("/api/files")
    async def list_files(thread_id: str = Query(...)):
        _validate_uuid(thread_id)
        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload="updated",
            base_output="output",
        )
        output_dir = ws.output_dir
        if not output_dir.exists():
            return FileListResponse(thread_id=thread_id, files=[])

        flist = []
        for fpath in sorted(output_dir.iterdir()):
            if fpath.is_file():
                flist.append(
                    FileInfo(
                        name=fpath.name,
                        path=fpath.name,
                        size=fpath.stat().st_size,
                        media_type=_guess_media_type(fpath.name),
                    )
                )
        return FileListResponse(thread_id=thread_id, files=flist)

    @app.get("/api/download")
    async def download_file(thread_id: str = Query(...), path: str = Query(...)):
        _validate_uuid(thread_id)
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
        return FileResponse(
            str(resolved),
            media_type=_guess_media_type(path),
            filename=resolved.name,
        )

    # ── Citations ────────────────────────────────────────────────────────

    @app.get("/api/citations")
    async def get_citations(thread_id: str = Query(...)):
        _validate_uuid(thread_id)
        from app.research.runtime import CITATION_REPORT_FILENAME

        ws = SessionWorkspace.for_thread(
            thread_id=thread_id,
            base_upload="updated",
            base_output="output",
        )
        report_path = ws.output_dir / CITATION_REPORT_FILENAME
        if not report_path.exists():
            raise HTTPException(
                status_code=404,
                detail="no citation results for this thread",
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return CitationsResponse(thread_id=thread_id, report=report)

    # ── WebSocket ─────────────────────────────────────────────────────────

    @app.websocket("/ws/{thread_id}")
    async def websocket_endpoint(ws: WebSocket, thread_id: str):
        if not UUID_RE.fullmatch(thread_id):
            await ws.close(code=4000)
            return

        async with events.subscribe(thread_id) as subscription:
            await ws.accept()

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
                    for t in [get_task, overflow_task]:
                        if not t.done():
                            t.cancel()

            async def _recv_messages():
                while True:
                    try:
                        data = await ws.receive_text()
                        msg = json.loads(data)
                        if msg.get("type") == "ping":
                            await ws.send_text(HeartbeatMessage().model_dump_json())
                    except (WebSocketDisconnect, Exception):
                        return

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
    mapping: dict[str, str] = {
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
    }
    return mapping.get(ext, "application/octet-stream")
