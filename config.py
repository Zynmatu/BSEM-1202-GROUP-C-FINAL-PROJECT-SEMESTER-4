# config.py — centralised settings loaded from .env
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "HR Management API"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/hr_db"
    sync_database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/hr_db"

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()          # instantiated once; reused on every import
def get_settings() -> Settings:
    return Settings()
