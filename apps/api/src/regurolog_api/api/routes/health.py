from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError

from regurolog_api.api.dependencies import get_database
from regurolog_api.contracts import HealthResponse, ReadinessResponse
from regurolog_api.database import Database
from regurolog_api.errors import ApiError

router = APIRouter()
DatabaseDependency = Annotated[Database, Depends(get_database)]


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Process liveness",
)
async def live() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {}},
    summary="Database readiness",
)
async def ready(database: DatabaseDependency) -> ReadinessResponse:
    try:
        await database.ping()
    except SQLAlchemyError as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Ma'lumotlar bazasi tayyor emas") from error
    return ReadinessResponse()
