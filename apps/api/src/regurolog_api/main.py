import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
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
        try:
            yield
        finally:
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
    return application


app = create_app()
