from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://recapz:recapz@localhost:5432/recapz"
    cors_origins: list[str] = ["http://localhost:5173"]
    worker_poll_interval_seconds: float = 2.0
    job_max_attempts: int = 3
    job_stale_after_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
