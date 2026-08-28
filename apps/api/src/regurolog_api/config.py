import hashlib
import hmac
import os
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


def derive_secret(master: str, label: str) -> str:
    """Deterministically derive an independent secret from the admin token.

    Using HMAC-SHA256 with a distinct label per purpose yields cryptographically
    independent 64-byte-hex secrets that stay stable across restarts and
    redeploys, so sessions remain valid and encrypted data stays readable as long
    as ADMIN_TOKEN is unchanged.
    """

    return hmac.new(
        master.encode("utf-8"),
        f"regurolog/v1/{label}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _running_on_railway() -> bool:
    return any(
        os.getenv(name)
        for name in ("RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID", "RAILWAY_ENVIRONMENT_NAME")
    )


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
    app_encryption_key: SecretStr | None = Field(
        default=None, validation_alias="APP_ENCRYPTION_KEY"
    )
    webhook_secret: SecretStr | None = Field(default=None, validation_alias="WEBHOOK_SECRET")
    public_base_url: str | None = Field(default=None, validation_alias="PUBLIC_BASE_URL")
    allowed_origins_value: str = Field(
        default="http://127.0.0.1:4173,http://localhost:5173",
        validation_alias="ALLOWED_ORIGINS",
    )
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    trust_proxy_headers: bool = Field(default=False, validation_alias="TRUST_PROXY_HEADERS")
    root_session_ttl_seconds: int = Field(
        default=86_400,
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
    staff_session_ttl_seconds: int = Field(
        default=86_400,
        ge=1800,
        le=86_400,
        validation_alias="STAFF_SESSION_TTL_SECONDS",
    )
    staff_idle_timeout_seconds: int = Field(
        default=7200,
        ge=300,
        le=7200,
        validation_alias="STAFF_IDLE_TIMEOUT_SECONDS",
    )
    login_challenge_ttl_seconds: int = Field(
        default=120,
        ge=60,
        le=600,
        validation_alias="LOGIN_CHALLENGE_TTL_SECONDS",
    )
    invite_ttl_seconds: int = Field(
        default=86_400,
        ge=3600,
        le=604_800,
        validation_alias="INVITE_TTL_SECONDS",
    )
    booking_horizon_days: int = Field(
        default=90,
        ge=1,
        le=365,
        validation_alias="BOOKING_HORIZON_DAYS",
    )
    no_show_grace_minutes: int = Field(
        default=30,
        ge=0,
        le=240,
        validation_alias="NO_SHOW_GRACE_MINUTES",
    )
    worker_poll_seconds: float = Field(
        default=1.0,
        ge=0.2,
        le=30,
        validation_alias="WORKER_POLL_SECONDS",
    )
    inbox_payload_retention_hours: int = Field(
        default=24,
        ge=1,
        le=720,
        validation_alias="INBOX_PAYLOAD_RETENTION_HOURS",
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
    def finalize_settings(self) -> "Settings":
        self._apply_automatic_defaults()
        self._validate_hosted_safety()
        return self

    def _apply_automatic_defaults(self) -> None:
        """Fill in everything derivable so ADMIN_TOKEN is the only required secret.

        A bare Railway deploy that only sets ADMIN_TOKEN (and the platform-provided
        DATABASE_URL) becomes a hosted, secure service without a dozen hand-set
        variables. Explicitly provided values are always respected.
        """

        env_explicit = "REGUROLOG_ENV" in os.environ or "ENVIRONMENT" in os.environ
        if _running_on_railway() and not env_explicit:
            self.environment = AppEnvironment.PRODUCTION

        # Derive the remaining secrets from ADMIN_TOKEN when they are not set.
        if self.admin_token is not None:
            master = self.admin_token.get_secret_value()
            if self.session_secret is None:
                self.session_secret = SecretStr(derive_secret(master, "session-secret"))
            if self.app_encryption_key is None:
                self.app_encryption_key = SecretStr(derive_secret(master, "encryption-key"))
            if self.webhook_secret is None:
                self.webhook_secret = SecretStr(derive_secret(master, "webhook-secret"))

        # Public URL (Telegram webhook + CORS) falls back to Railway's domain.
        if self.public_base_url is None:
            railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
            if railway_domain:
                self.public_base_url = f"https://{railway_domain}"

        # Behind Railway's edge the app always sits behind a TLS-terminating proxy.
        if self.environment in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            self.cookie_secure = True
            self.trust_proxy_headers = True

    def _validate_hosted_safety(self) -> None:
        if self.environment not in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}:
            return

        missing = [
            name
            for name, value in (
                ("DATABASE_URL", self.database_url),
                ("ADMIN_TOKEN", self.admin_token),
            )
            if value is None
        ]
        if missing:
            raise ValueError(f"Hosted muhit uchun majburiy sozlamalar yo'q: {', '.join(missing)}")

        # Secrets are always populated by now (derived from ADMIN_TOKEN); the
        # strength checks stay to reject weak values if any are set by hand.
        for name, secret in (
            ("ADMIN_TOKEN", self.admin_token),
            ("SESSION_SECRET", self.session_secret),
            ("APP_ENCRYPTION_KEY", self.app_encryption_key),
            ("WEBHOOK_SECRET", self.webhook_secret),
        ):
            if secret is None:
                continue
            raw = secret.get_secret_value()
            if len(raw.encode()) < 32 or raw.startswith("replace-with-"):
                raise ValueError(f"{name} kamida 32 byte bo'lishi kerak")

        if self.public_base_url is not None:
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


def normalize_database_url(url: str) -> str:
    """Convert Railway's PostgreSQL URL to SQLAlchemy's psycopg driver URL."""

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
