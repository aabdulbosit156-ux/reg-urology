import pytest
from httpx import ASGITransport, AsyncClient
from regurolog_api.contracts import (
    APPOINTMENT_DURATION_MINUTES,
    BUSINESS_TIMEZONE_NAME,
    AppointmentStatus,
    ContactAttemptOutcome,
    StaffRole,
)
from regurolog_api.main import create_app


def test_domain_contract_baseline() -> None:
    assert BUSINESS_TIMEZONE_NAME == "Asia/Tashkent"
    assert APPOINTMENT_DURATION_MINUTES == 15
    assert set(StaffRole) == {StaffRole.DEV, StaffRole.DIRECTOR, StaffRole.ADMIN}
    assert ContactAttemptOutcome.ANSWERED.value == "answered"
    assert AppointmentStatus.NO_SHOW.value == "no_show"


@pytest.mark.asyncio
async def test_live_health_and_openapi() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health/live")
        openapi = await client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "regurolog-api",
        "timezone": "Asia/Tashkent",
    }
    assert openapi.json()["info"]["title"] == "RegUrolog API"


@pytest.mark.asyncio
async def test_missing_session_uses_standard_error_contract() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me", headers={"X-Request-ID": "contract-test"})

    assert response.status_code == 401
    assert response.headers["x-request-id"] == "contract-test"
    assert response.json() == {
        "code": "AUTH_REQUIRED",
        "message": "Tizimga kirish talab qilinadi",
        "field_errors": [],
        "request_id": "contract-test",
    }


@pytest.mark.asyncio
async def test_unknown_route_uses_standard_error_contract() -> None:
    transport = ASGITransport(app=create_app())

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/not-a-route")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["field_errors"] == []
