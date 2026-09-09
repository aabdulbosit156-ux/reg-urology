from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/regurolog"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    dev_username: str = "dev"
    dev_password_hash: str = ""

    bot_internal_secret: str = "dev-internal-secret-change-me"
    bot_username: str = ""
    bot_token: str = ""
    staff_session_ttl_minutes: int = 15

    api_base_url: str = "http://localhost:8000"
    webapp_url: str = ""
    storage_chat_id: int | None = None
    analysis_tmp_dir: str = "./tmp/analysis"

    cors_origins: list[str] = ["http://localhost:5173"]

    @field_validator("storage_chat_id", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url", mode="before")
    @classmethod
    def _force_asyncpg_driver(cls, value: object) -> object:
        # Railway (and other PaaS) inject DATABASE_URL as postgres:// or postgresql://,
        # which makes SQLAlchemy default to the sync psycopg2 driver — not installed here,
        # since this app only uses the async asyncpg driver.
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return "postgresql+asyncpg://" + value[len("postgres://") :]
            if value.startswith("postgresql://"):
                return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
