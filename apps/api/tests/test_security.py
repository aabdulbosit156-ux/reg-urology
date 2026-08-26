import pytest
from pydantic import ValidationError
from regurolog_api.config import Settings, normalize_database_url
from regurolog_api.security import constant_time_token_matches, keyed_digest


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
