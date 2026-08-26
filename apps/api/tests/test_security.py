import pytest
from pydantic import ValidationError
from regurolog_api.api.dependencies import request_source
from regurolog_api.config import Settings, normalize_database_url
from regurolog_api.security import constant_time_token_matches, keyed_digest
from starlette.requests import Request


def test_railway_database_url_uses_psycopg_driver() -> None:
    assert (
        normalize_database_url("postgres://user:pass@postgres.railway.internal:5432/app")
        == "postgresql+psycopg://user:pass@postgres.railway.internal:5432/app"
    )
    assert normalize_database_url("postgresql+psycopg://already-normal/app") == (
        "postgresql+psycopg://already-normal/app"
    )


def test_security_digests_are_deterministic_without_exposing_input() -> None:
    assert constant_time_token_matches("same-token", "same-token") is True
    assert constant_time_token_matches("wrong-token", "same-token") is False
    digest = keyed_digest("sensitive-value", "independent-secret")
    assert digest == keyed_digest("sensitive-value", "independent-secret")
    assert "sensitive-value" not in digest


def test_production_rejects_insecure_or_missing_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                "REGUROLOG_ENV": "production",
                "DATABASE_URL": "postgresql://database/app",
                "ADMIN_TOKEN": "short",
                "SESSION_SECRET": "short",
                "PUBLIC_BASE_URL": "http://example.test",
                "COOKIE_SECURE": False,
            }
        )


def test_trusted_proxy_source_does_not_use_spoofable_leftmost_value() -> None:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/root",
            "headers": [(b"x-forwarded-for", b"spoofed, 203.0.113.9")],
            "client": ("10.0.0.2", 1234),
        }
    )
    settings = Settings.model_validate({"TRUST_PROXY_HEADERS": True})

    assert request_source(request, settings) == "203.0.113.9"
