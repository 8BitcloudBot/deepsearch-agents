"""FastAPI boundary for the schema 5.0 multi-turn conversation product."""

from __future__ import annotations

import asyncio
import mimetypes
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.api.events import ConversationEventBus
from app.api.schemas import (
    AdminUserResponse,
    AttachmentResponse,
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    TurnResponse,
    TurnStartRequest,
    TurnStartResponse,
    UserResponse,
)
from app.conversation.application import ConversationApplication
from app.conversation.report import ConversationReport
from app.conversation.store import (
    Attachment,
    Conversation,
    ConversationStore,
    Turn,
    User,
)

_COOKIE = "deepsearch_session"
_MAX_FILE_SIZE = 25 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".xlsx"}


def create_app(
    *,
    store: ConversationStore | None = None,
    conversation_application: ConversationApplication | Any | None = None,
    upload_root: str | Path | None = None,
    events: ConversationEventBus | None = None,
) -> FastAPI:
    """Build an isolated application; dependencies are injectable for tests."""

    if store is None:
        store = ConversationStore(
            Path(os.getenv("DEEPSEARCH_SQLITE", ".data/conversations.sqlite3"))
        )
    if upload_root is None:
        upload_root = Path(os.getenv("DEEPSEARCH_UPLOAD_ROOT", ".data/uploads"))
    upload_root = Path(upload_root)
    report = getattr(conversation_application, "report", None)
    if report is None:
        report = ConversationReport(
            Path(os.getenv("DEEPSEARCH_REPORT_ROOT", ".data/reports")), store
        )
    if events is None:
        events = ConversationEventBus()

    app = FastAPI(title="deepsearch-conversation", version="5.0.0")
    app.state.store = store
    app.state.conversation_application = conversation_application
    app.state.events = events
    app.state.turn_tasks: set[asyncio.Task[Any]] = set()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5181",
            "http://localhost:5181",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    def current_user(request: Request) -> User:
        user = store.resolve_session(request.cookies.get(_COOKIE))
        if user is None:
            raise HTTPException(status_code=401, detail="authentication required")
        return user

    def user_response(user: User) -> UserResponse:
        return UserResponse(id=user.id, username=user.username, role=user.role)

    def attachment_response(item: Attachment) -> AttachmentResponse:
        return AttachmentResponse(
            id=item.id,
            name=item.name,
            size=item.size,
            media_type=item.media_type,
            active=item.active,
        )

    def turn_response(item: Turn) -> TurnResponse:
        return TurnResponse(
            id=item.id,
            question=item.question,
            answer=item.answer,
            use_web=item.use_web,
            status=item.status,
            attachment_ids=list(item.attachment_ids),
            result=item.result,
            created_at=item.created_at,
            completed_at=item.completed_at,
        )

    def conversation_response(
        user: User, conversation: Conversation
    ) -> ConversationResponse:
        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            owner_id=conversation.owner_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            turns=[
                turn_response(item) for item in store.list_turns(user, conversation.id)
            ],
            attachments=[
                attachment_response(item)
                for item in store.list_attachments(user, conversation.id)
            ],
        )

    def require_conversation(user: User, conversation_id: str) -> Conversation:
        try:
            return store.get_conversation(user, conversation_id)
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail="conversation not found"
            ) from exc

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        capabilities = getattr(
            conversation_application,
            "capabilities",
            {
                source: {"status": "unavailable"}
                for source in ("model", "knowledge", "web", "session_file")
            },
        )
        return HealthResponse(
            status="ok",
            capabilities=capabilities,
        )

    @app.post("/api/auth/login", response_model=LoginResponse)
    async def login(body: LoginRequest) -> LoginResponse:
        user = store.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = store.create_session(user)
        from fastapi.responses import JSONResponse

        result = JSONResponse(
            content=LoginResponse(user=user_response(user)).model_dump()
        )
        result.set_cookie(
            _COOKIE,
            token,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=7 * 24 * 60 * 60,
        )
        return result  # type: ignore[return-value]

    @app.post("/api/auth/logout", status_code=204)
    async def logout(request: Request) -> None:
        token = request.cookies.get(_COOKIE)
        if token:
            store.delete_session(token)

    @app.get("/api/auth/me", response_model=UserResponse)
    async def me(user: User = Depends(current_user)) -> UserResponse:
        return user_response(user)

    @app.get("/api/admin/users", response_model=list[AdminUserResponse])
    async def admin_users(
        user: User = Depends(current_user),
    ) -> list[AdminUserResponse]:
        try:
            summaries = store.admin_user_summaries(user)
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail="administrator access required"
            ) from exc
        return [
            AdminUserResponse(
                id=item.id,
                username=item.username,
                role=item.role,
                conversation_count=item.conversation_count,
            )
            for item in summaries
        ]

    @app.delete("/api/admin/users/{user_id}/data", status_code=204)
    async def admin_delete_user_data(
        user_id: str, user: User = Depends(current_user)
    ) -> None:
        try:
            store.admin_delete_user_data(user, user_id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=403, detail="administrator access required"
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="administrator data cannot be deleted here"
            ) from exc

    @app.get("/api/conversations", response_model=list[ConversationResponse])
    async def list_conversations(
        user: User = Depends(current_user),
    ) -> list[ConversationResponse]:
        return [
            conversation_response(user, item) for item in store.list_conversations(user)
        ]

    @app.post(
        "/api/conversations", response_model=ConversationResponse, status_code=201
    )
    async def create_conversation(
        body: ConversationCreateRequest,
        user: User = Depends(current_user),
    ) -> ConversationResponse:
        try:
            item = store.create_conversation(user, body.title)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="invalid conversation title"
            ) from exc
        return conversation_response(user, item)

    @app.get(
        "/api/conversations/{conversation_id}", response_model=ConversationResponse
    )
    async def get_conversation(
        conversation_id: str, user: User = Depends(current_user)
    ) -> ConversationResponse:
        return conversation_response(user, require_conversation(user, conversation_id))

    @app.patch(
        "/api/conversations/{conversation_id}", response_model=ConversationResponse
    )
    async def rename_conversation(
        conversation_id: str,
        body: ConversationRenameRequest,
        user: User = Depends(current_user),
    ) -> ConversationResponse:
        require_conversation(user, conversation_id)
        try:
            item = store.rename_conversation(user, conversation_id, body.title)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="invalid conversation title"
            ) from exc
        return conversation_response(user, item)

    @app.delete("/api/conversations/{conversation_id}", status_code=204)
    async def delete_conversation(
        conversation_id: str, user: User = Depends(current_user)
    ) -> None:
        require_conversation(user, conversation_id)
        store.delete_conversation(user, conversation_id)

    @app.post(
        "/api/conversations/{conversation_id}/turns",
        response_model=TurnStartResponse,
        status_code=202,
    )
    async def start_turn(
        conversation_id: str,
        body: TurnStartRequest,
        user: User = Depends(current_user),
    ) -> TurnStartResponse:
        require_conversation(user, conversation_id)
        application = conversation_application
        if application is None:
            raise HTTPException(
                status_code=503, detail="conversation engine unavailable"
            )
        try:
            turn = await application.submit(
                user, conversation_id, question=body.question, use_web=body.use_web
            )
        except (LookupError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="invalid turn") from exc
        events.emit(
            conversation_id, turn.id, "turn.started", "本轮分析已开始", stage="started"
        )
        task = asyncio.create_task(
            _execute_turn(application, user, conversation_id, turn.id, events)
        )
        app.state.turn_tasks.add(task)
        task.add_done_callback(app.state.turn_tasks.discard)
        return TurnStartResponse(
            turn_id=turn.id, conversation_id=conversation_id, use_web=turn.use_web
        )

    @app.get(
        "/api/conversations/{conversation_id}/turns/{turn_id}",
        response_model=TurnResponse,
    )
    async def get_turn(
        conversation_id: str,
        turn_id: str,
        user: User = Depends(current_user),
    ) -> TurnResponse:
        require_conversation(user, conversation_id)
        try:
            return turn_response(store.get_turn(user, conversation_id, turn_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="turn not found") from exc

    @app.post(
        "/api/conversations/{conversation_id}/files",
        response_model=list[AttachmentResponse],
        status_code=201,
    )
    async def upload_files(
        conversation_id: str,
        files: list[UploadFile] = File(...),
        user: User = Depends(current_user),
    ) -> list[AttachmentResponse]:
        require_conversation(user, conversation_id)
        destination = upload_root / user.id / conversation_id
        destination.mkdir(parents=True, exist_ok=True)
        created: list[AttachmentResponse] = []
        for upload in files:
            name = Path(upload.filename or "").name
            if not name or Path(name).suffix.lower() not in _ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=422, detail="unsupported attachment")
            data = await upload.read(_MAX_FILE_SIZE + 1)
            if len(data) > _MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="attachment too large")
            stored = destination / f"{secrets.token_hex(8)}-{name}"
            stored.write_bytes(data)
            item = store.add_attachment(
                user,
                conversation_id,
                name=name,
                stored_path=str(stored),
                size=len(data),
                media_type=upload.content_type
                or mimetypes.guess_type(name)[0]
                or "application/octet-stream",
            )
            indexer = getattr(conversation_application, "index_attachment", None)
            if callable(indexer):
                try:
                    indexer(user, conversation_id, item)
                except Exception as exc:
                    store.remove_attachment(user, conversation_id, item.id)
                    stored.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=422, detail="attachment could not be indexed"
                    ) from exc
            created.append(attachment_response(item))
        return created

    @app.get(
        "/api/conversations/{conversation_id}/files",
        response_model=list[AttachmentResponse],
    )
    async def list_files(
        conversation_id: str, user: User = Depends(current_user)
    ) -> list[AttachmentResponse]:
        require_conversation(user, conversation_id)
        return [
            attachment_response(item)
            for item in store.list_attachments(user, conversation_id)
        ]

    @app.delete(
        "/api/conversations/{conversation_id}/files/{attachment_id}",
        response_model=AttachmentResponse,
    )
    async def remove_file(
        conversation_id: str,
        attachment_id: str,
        user: User = Depends(current_user),
    ) -> AttachmentResponse:
        require_conversation(user, conversation_id)
        try:
            remover = getattr(conversation_application, "remove_attachment", None)
            if callable(remover):
                remover(user, conversation_id, attachment_id)
            return attachment_response(
                store.remove_attachment(user, conversation_id, attachment_id)
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="attachment not found") from exc

    @app.get("/api/conversations/{conversation_id}/report")
    async def download_report(
        conversation_id: str, user: User = Depends(current_user)
    ) -> FileResponse:
        require_conversation(user, conversation_id)
        path = store.report_path(user, conversation_id)
        if not path:
            raise HTTPException(status_code=404, detail="report not found")
        path = report.refresh(user, conversation_id)
        if not Path(path).is_file():
            raise HTTPException(status_code=404, detail="report not found")
        return FileResponse(
            path, media_type="text/markdown", filename="research-report.md"
        )

    @app.websocket("/api/conversations/{conversation_id}/events")
    async def conversation_events(websocket: WebSocket, conversation_id: str) -> None:
        user = store.resolve_session(websocket.cookies.get(_COOKIE))
        if user is None:
            await websocket.close(code=4401)
            return
        try:
            store.get_conversation(user, conversation_id)
        except LookupError:
            await websocket.close(code=4404)
            return
        await websocket.accept()
        async with events.subscribe(conversation_id) as subscription:
            sender = asyncio.create_task(_send_events(websocket, subscription))
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                sender.cancel()

    return app


async def _execute_turn(
    application: Any,
    user: User,
    conversation_id: str,
    turn_id: str,
    events: ConversationEventBus,
) -> None:
    def emit(payload: dict[str, Any]) -> None:
        event_type = payload.get("type")
        if event_type not in {
            "stage.changed",
            "answer.delta",
            "evidence.ready",
            "report.updated",
            "turn.completed",
            "turn.failed",
        }:
            return
        events.emit(
            conversation_id,
            turn_id,
            event_type,
            str(payload.get("message", "")),
            stage=payload.get("stage"),
            data=payload.get("data") or {},
        )

    await application.execute(user, conversation_id, turn_id, emit=emit)


async def _send_events(websocket: WebSocket, subscription: Any) -> None:
    while websocket.client_state == WebSocketState.CONNECTED:
        event = await subscription.queue.get()
        await websocket.send_text(event.model_dump_json())
