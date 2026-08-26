import os

import pytest
from httpx import ASGITransport, AsyncClient
from regurolog_api.config import Settings
from regurolog_api.main import create_app
from regurolog_api.models import AuditEvent, AuthThrottle, Session
from sqlalchemy import delete


@pytest.mark.integration
@pytest.mark.asyncio
async def test_root_login_session_and_logout_against_postgres() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL berilmagan")

    admin_token = "integration-admin-token-at-least-32-bytes"
    settings = Settings.model_validate(
        {
            "REGUROLOG_ENV": "test",
            "DATABASE_URL": database_url,
            "ADMIN_TOKEN": admin_token,
            "SESSION_SECRET": "integration-session-secret-at-least-32-bytes",
            "PUBLIC_BASE_URL": "http://test",
            "ALLOWED_ORIGINS": "http://test",
            "COOKIE_SECURE": False,
            "TRUST_PROXY_HEADERS": True,
        }
    )
    application = create_app(settings)

    async with application.router.lifespan_context(application):
        database = application.state.database
        async with database.session_factory() as db_session:
            async with db_session.begin():
                await db_session.execute(delete(AuditEvent))
                await db_session.execute(delete(Session))
                await db_session.execute(delete(AuthThrottle))

        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            invalid_attempts = [
                await client.post(
                    "/api/v1/auth/root",
                    json={"token": "wrong"},
                    headers={"Origin": "http://test", "X-Forwarded-For": "198.51.100.10"},
                )
                for _ in range(settings.root_login_max_attempts)
            ]
            rate_limited = await client.post(
                "/api/v1/auth/root",
                json={"token": "wrong"},
                headers={"Origin": "http://test", "X-Forwarded-For": "198.51.100.10"},
            )
            login = await client.post(
                "/api/v1/auth/root",
                json={"token": admin_token},
                headers={"Origin": "http://test", "X-Forwarded-For": "198.51.100.20"},
            )
            current = await client.get("/api/v1/auth/me")
            csrf_token = login.json()["csrf_token"]
            session_cookie = client.cookies.get("regurolog_session")
            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"Origin": "http://test", "X-CSRF-Token": csrf_token},
            )
            client.cookies.clear()
            after_logout = await client.get(
                "/api/v1/auth/me",
                headers={"Cookie": f"regurolog_session={session_cookie}"},
            )

        assert all(response.status_code == 401 for response in invalid_attempts)
        assert invalid_attempts[-1].json()["code"] == "ROOT_TOKEN_INVALID"
        assert rate_limited.status_code == 429
        assert rate_limited.json()["code"] == "ROOT_LOGIN_RATE_LIMITED"
        assert int(rate_limited.headers["retry-after"]) > 0
        assert login.status_code == 200
        assert "regurolog_session" in login.headers["set-cookie"]
        assert admin_token not in login.headers["set-cookie"]
        assert current.status_code == 200
        assert current.json()["principal"] == {"kind": "root", "role": "DEV"}
        assert logout.status_code == 204
        assert after_logout.status_code == 401

        async with database.session_factory() as db_session:
            async with db_session.begin():
                await db_session.execute(delete(AuditEvent))
                await db_session.execute(delete(Session))
                await db_session.execute(delete(AuthThrottle))
