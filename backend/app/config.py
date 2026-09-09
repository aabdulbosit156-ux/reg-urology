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


@lru_cache
def get_settings() -> Settings:
    return Settings()
