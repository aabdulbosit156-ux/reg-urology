from enum import StrEnum
from functools import cached_property
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime configuration. Secrets are never rendered in repr or API responses."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        validation_alias=AliasChoices("REGUROLOG_ENV", "ENVIRONMENT"),
    )
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    admin_token: SecretStr | None = Field(default=None, validation_alias="ADMIN_TOKEN")
    session_secret: SecretStr | None = Field(default=None, validation_alias="SESSION_SECRET")
    public_base_url: str | None = Field(default=None, validation_alias="PUBLIC_BASE_URL")
    allowed_origins_value: str = Field(
        default="http://127.0.0.1:4173,http://localhost:5173",
        validation_alias="ALLOWED_ORIGINS",
    )
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    trust_proxy_headers: bool = Field(default=False, validation_alias="TRUST_PROXY_HEADERS")
    root_session_ttl_seconds: int = Field(
        default=3600,
        ge=300,
        le=86_400,
        validation_alias="ROOT_SESSION_TTL_SECONDS",
    )
    root_login_max_attempts: int = Field(
        default=5,
        ge=2,
        le=20,
        validation_alias="ROOT_LOGIN_MAX_ATTEMPTS",
    )
    root_login_window_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        validation_alias="ROOT_LOGIN_WINDOW_SECONDS",
    )
    root_login_block_seconds: int = Field(
        default=900,
        ge=60,
        le=86_400,
        validation_alias="ROOT_LOGIN_BLOCK_SECONDS",
    )

    @cached_property
    def allowed_origins(self) -> frozenset[str]:
        origins = {
            origin.strip().rstrip("/")
            for origin in self.allowed_origins_value.split(",")
            if origin.strip()
        }
        if self.public_base_url:
            origins.add(self.public_base_url.rstrip("/"))
        return frozenset(origins)

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment not in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            return self

        missing = [
            name
            for name, value in (
                ("DATABASE_URL", self.database_url),
                ("ADMIN_TOKEN", self.admin_token),
                ("SESSION_SECRET", self.session_secret),
                ("PUBLIC_BASE_URL", self.public_base_url),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"Hosted muhit uchun majburiy sozlamalar yo'q: {', '.join(missing)}")

        assert self.admin_token is not None
        assert self.session_secret is not None
        assert self.public_base_url is not None
        admin_token = self.admin_token.get_secret_value()
        session_secret = self.session_secret.get_secret_value()
        if len(admin_token.encode()) < 32 or admin_token.startswith("replace-with-"):
            raise ValueError("ADMIN_TOKEN kamida 32 byte bo'lishi kerak")
        if len(session_secret.encode()) < 32 or session_secret.startswith("replace-with-"):
            raise ValueError("SESSION_SECRET kamida 32 byte bo'lishi kerak")
        public_url = urlsplit(self.public_base_url)
        if (
            public_url.scheme != "https"
            or not public_url.netloc
            or public_url.username is not None
            or public_url.password is not None
            or public_url.path not in {"", "/"}
            or public_url.query
            or public_url.fragment
        ):
            raise ValueError("PUBLIC_BASE_URL path/querysiz to'liq https origin bo'lishi kerak")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE hosted muhitda true bo'lishi kerak")
        return self


def normalize_database_url(url: str) -> str:
    """Convert Railway's PostgreSQL URL to SQLAlchemy's psycopg driver URL."""

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
