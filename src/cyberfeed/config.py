"""Application configuration via pydantic-settings."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "CyberFeed"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "CHANGE-ME-TO-A-RANDOM-STRING-AT-LEAST-32-CHARS!!"  # noqa: S105
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000"]

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/cyberfeed.db"

    # Auth
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REGISTRATION_OPEN: bool = True

    # Rate limiting
    RATE_LIMIT_API: str = "60/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # LLM
    LLM_ENABLED: bool = False
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = ""
    LLM_TIMEOUT: int = 30
    LLM_MAX_TOKENS: int = 300

    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ENABLED: bool = False

    # Email / SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_USE_TLS: bool = True
    EMAIL_ENABLED: bool = False

    # Scheduler
    COLLECT_DEFAULT_INTERVAL_MIN: int = 30

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
