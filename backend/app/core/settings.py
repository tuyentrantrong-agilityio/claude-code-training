from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-secret-key-do-not-use-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://recapz:recapz@localhost:5432/recapz"
    cors_origins: list[str] = ["http://localhost:5173"]
    worker_poll_interval_seconds: float = 2.0
    job_max_attempts: int = 3
    job_stale_after_seconds: int = 600
    secret_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    frontend_url: str = "http://localhost:5173"
    session_ttl_days: int = 14
    invite_ttl_days: int = 7

    @model_validator(mode="after")
    def _require_secret_key(self) -> Self:
        if not self.secret_key:
            if self.app_env != "development":
                raise ValueError("SECRET_KEY is required when APP_ENV is not development")
            self.secret_key = DEV_SECRET_KEY
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
