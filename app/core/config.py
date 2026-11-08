"""
Application configuration using pydantic-settings.

Loads environment variables from .env file with type validation and
graceful handling of missing optional keys.

Non-negotiable rules:
- Fyers API v3 is the ONLY data source
- Kotak Neo is the ONLY execution broker
- xAI Grok is the ONLY AI for financial news
- PostgreSQL only (no SQLite)
- All timestamps in IST (Asia/Kolkata)
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # 1. Database & Cache (required)
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://user:password@localhost:5432/trading_platform",
        description="PostgreSQL connection string",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # -------------------------------------------------------------------------
    # 2. Fyers API v3 (Market Data - ONLY data source)
    # -------------------------------------------------------------------------
    FYERS_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="Fyers API client ID",
    )
    FYERS_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Fyers API secret key",
    )
    FYERS_REDIRECT_URI: Optional[str] = Field(
        default="http://localhost:8000/api/v1/fyers/auth/callback",
        description="Fyers OAuth2 redirect URI",
    )

    # -------------------------------------------------------------------------
    # 3. Kotak Neo (Execution - ONLY broker for order placement)
    # -------------------------------------------------------------------------
    KOTAK_CONSUMER_KEY: Optional[str] = Field(
        default=None,
        description="Kotak Neo consumer key",
    )
    KOTAK_MOBILE_NUMBER: Optional[str] = Field(
        default=None,
        description="Kotak Neo mobile number",
    )
    KOTAK_UCC: Optional[str] = Field(
        default=None,
        description="Kotak Neo UCC",
    )
    KOTAK_MPIN: Optional[str] = Field(
        default=None,
        description="Kotak Neo MPIN",
    )
    KOTAK_TOTP_SECRET: Optional[str] = Field(
        default=None,
        description="Kotak Neo TOTP secret",
    )

    # -------------------------------------------------------------------------
    # 4. xAI Grok (AI Brain - financial news analysis ONLY)
    # -------------------------------------------------------------------------
    XAI_API_KEY: Optional[str] = Field(
        default=None,
        description="xAI Grok API key (starts with xai-)",
    )
    XAI_MODEL: Optional[str] = Field(
        default="grok-beta",
        description="xAI Grok model name",
    )

    # -------------------------------------------------------------------------
    # 5. Telegram Alerts
    # -------------------------------------------------------------------------
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Telegram bot token",
    )
    TELEGRAM_CHAT_ID: Optional[str] = Field(
        default=None,
        description="Telegram chat ID",
    )

    # -------------------------------------------------------------------------
    # Application settings
    # -------------------------------------------------------------------------
    APP_HOST: str = Field(default="0.0.0.0", description="Application host")
    APP_PORT: int = Field(default=8000, description="Application port")
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="CORS allowed origins (comma-separated)",
    )

    # Timezone (IST only)
    TZ: str = Field(default="Asia/Kolkata", description="Application timezone")


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the settings singleton."""
    return settings
