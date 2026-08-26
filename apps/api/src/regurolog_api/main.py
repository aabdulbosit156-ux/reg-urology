import asyncio
import logging
import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from regurolog_api import __version__
from regurolog_api.api.router import api_router
from regurolog_api.config import AppEnvironment, Settings
from regurolog_api.contracts import ErrorResponse, FieldError
from regurolog_api.database import Database
from regurolog_api.domain.validation import DomainValidationError
from regurolog_api.errors import ApiError

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
logger = logging.getLogger(__name__)

# When REGUROLOG_PROCESS is "all" (the default single-service deploy) this one
# process also runs the Telegram worker loop and serves the built frontend.
_PROCESS_MODE = os.getenv("REGUROLOG_PROCESS", "all").strip().lower()
_RUN_WORKER_IN_PROCESS = _PROCESS_MODE == "all"

_STATIC_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; "
        "form-action 'self'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


def _frontend_directory() -> Path | None:
    """Resolve the built frontend directory, if present.

    Defaults to the location baked into the single-service container image and
    can be overridden with WEB_DIST_DIR for local runs.
    """

    configured = os.getenv("WEB_DIST_DIR", "/app/web")
    candidate = Path(configured).resolve()
    return candidate if (candidate / "index.html").is_file() else None


def _static_response(path: Path) -> FileResponse:
    cache = (
        "no-cache"
        if path.name == "index.html"
        else "public, max-age=31536000, immutable"
    )
    return FileResponse(path, headers={**_STATIC_SECURITY_HEADERS, "Cache-Control": cache})


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        field_errors=field_errors or [],
        request_id=_request_id(request),
    )
    response_headers = {"Cache-Control": "no-store", **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=response_headers,
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings()
    hosted = runtime_settings.environment in {
        AppEnvironment.STAGING,
        AppEnvironment.PRODUCTION,
    }

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        database = (
            Database(runtime_settings.database_url) if runtime_settings.database_url else None
        )
        application.state.database = database

        stop_event: asyncio.Event | None = None
        worker_task: asyncio.Task[None] | None = None
        if (
            _RUN_WORKER_IN_PROCESS
            and database is not None
            and runtime_settings.environment is not AppEnvironment.TEST
        ):
            # Lazy import keeps the aiogram dependency out of the import path when
            # the worker is not co-hosted (REGUROLOG_PROCESS=api).
            from regurolog_api.worker import Worker, run_worker_loop

            try:
                worker = Worker(runtime_settings, database)
            except Exception:  # noqa: BLE001 - degrade to API-only if bot unconfigured
                logger.exception("Worker ishga tushmadi; API worker'siz davom etadi")
            else:
                stop_event = asyncio.Event()
                worker_task = asyncio.create_task(
                    run_worker_loop(worker, stop_event, runtime_settings.worker_poll_seconds)
                )

        try:
            yield
        finally:
            if stop_event is not None:
                stop_event.set()
            if worker_task is not None:
                try:
                    await asyncio.wait_for(worker_task, timeout=10)
                except (TimeoutError, asyncio.CancelledError):
                    worker_task.cancel()
            if database is not None:
                await database.close()

    application = FastAPI(
        title="RegUrolog API",
        version=__version__,
        docs_url=None if hosted else "/api/docs",
        redoc_url=None,
        openapi_url=None if hosted else "/api/v1/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.database = None

    @application.middleware("http")
    async def request_metadata(request: Request, call_next):  # type: ignore[no-untyped-def]
        incoming_id = request.headers.get("x-request-id", "")
        request.state.request_id = (
            incoming_id if REQUEST_ID_PATTERN.fullmatch(incoming_id) else uuid4().hex
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if hosted:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @application.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
        return _error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            field_errors=error.field_errors,
            headers=error.headers,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        field_errors = [
            FieldError(
                field=".".join(str(part) for part in item["loc"] if part != "body"),
                message=str(item["msg"]),
            )
            for item in error.errors()
        ]
        return _error_response(
            request,
            status_code=422,
            code="VALIDATION_ERROR",
            message="Kiritilgan ma'lumotlarni tekshiring",
            field_errors=field_errors,
        )

    @application.exception_handler(DomainValidationError)
    async def domain_validation_error_handler(
        request: Request,
        error: DomainValidationError,
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="DOMAIN_VALIDATION_ERROR",
            message=error.message,
            field_errors=[FieldError(field=error.field, message=error.message)],
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        code = "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR"
        message = "Manzil topilmadi" if error.status_code == 404 else "So'rov bajarilmadi"
        return _error_response(
            request,
            status_code=error.status_code,
            code=code,
            message=message,
            headers=dict(error.headers or {}),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
        logger.exception("Unhandled API error; request_id=%s", _request_id(request), exc_info=error)
        return _error_response(
            request,
            status_code=500,
            code="INTERNAL_ERROR",
            message="Serverda kutilmagan xato yuz berdi",
        )

    application.include_router(api_router, prefix="/api/v1")

    frontend_directory = _frontend_directory()
    if frontend_directory is not None:
        index_file = frontend_directory / "index.html"

        @application.get("/{full_path:path}", include_in_schema=False)
        async def serve_frontend(full_path: str) -> Response:
            # Unknown API paths stay JSON 404s instead of the SPA shell.
            if full_path == "api" or full_path.startswith("api/"):
                raise ApiError(404, "NOT_FOUND", "Manzil topilmadi")
            if full_path:
                candidate = (frontend_directory / full_path).resolve()
                if candidate.is_relative_to(frontend_directory) and candidate.is_file():
                    return _static_response(candidate)
            # SPA fallback: let the client-side router resolve the path.
            return _static_response(index_file)

    return application


app = create_app()
