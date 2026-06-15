"""
config.py — Centralised application settings loaded from environment / .env file.
Uses pydantic-settings for type-safe configuration and validation.
"""
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, EmailStr, field_validator
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "HR Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ── Security ─────────────────────────────────────────────────────────────
    # Fallback generates a fresh key each restart (dev-only safety net).
    SECRET_KEY: str = secrets.token_hex(64)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://hruser:hrpassword@localhost:5432/hrdb"
    SYNC_DATABASE_URL: str = "postgresql://hruser:hrpassword@localhost:5432/hrdb"

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── Company ──────────────────────────────────────────────────────────────
    COMPANY_NAME: str = "Apex Corp HR"
    SUPPORT_EMAIL: str = "hr-support@apexcorp.com"


settings = Settings()
