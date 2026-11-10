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

from typing import List, Optional
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
    # 1. GENERAL SETTINGS
    # -------------------------------------------------------------------------
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment: development, staging, production",
    )
    DEBUG: bool = Field(
        default=True,
        description="Enable debug mode",
    )

    # -------------------------------------------------------------------------
    # 2. SECURITY & AUTH
    # -------------------------------------------------------------------------
    SECRET_KEY: str = Field(
        default="generate_a_random_secure_string_here",
        description="Secret key for session/cookie signing",
    )
    JWT_SECRET: str = Field(
        default="generate_another_random_secure_string_here",
        description="JWT signing secret",
    )
    JWT_TTL_MINUTES: int = Field(
        default=720,
        description="JWT token TTL in minutes",
    )
    ADMIN_EMAIL: str = Field(
        default="agaffoor68@gmail.com",
        description="Default admin email",
    )
    ADMIN_PASSWORD: str = Field(
        default="Abdul@222",
        description="Default admin password",
    )

    # -------------------------------------------------------------------------
    # 3. DATABASE & CACHE
    # -------------------------------------------------------------------------
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://user:password@localhost:5432/alphatrade",
        description="PostgreSQL connection string",
    )
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # -------------------------------------------------------------------------
    # 4. FYERS API v3 (Market Data - ONLY data source)
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
        default="http://localhost:8000/api/v1/fyers/callback",
        description="Fyers OAuth2 redirect URI",
    )
    FYERS_ACCESS_TOKEN: str = Field(
        default="",
        description="Fyers API access token (auto-updated after OAuth)",
    )
    FYERS_REFRESH_TOKEN: str = Field(
        default="",
        description="Fyers API refresh token (if available)",
    )
    FYERS_API_BASE: str = Field(
        default="https://api-t1.fyers.in/api",
        description="Fyers API base URL (v3)",
    )
    FYERS_SYMBOL_MASTER_BASE: str = Field(
        default="https://public.fyers.in/sym_details/",
        description="Base URL for Fyers Symbol Master CSV files",
    )

    # -------------------------------------------------------------------------
    # 5. KOTAK NEO (Execution - ONLY broker for order placement)
    # -------------------------------------------------------------------------
    KOTAK_CONSUMER_KEY: Optional[str] = Field(
        default=None,
        description="Kotak Neo consumer key",
    )
    KOTAK_TOTP_SECRET: Optional[str] = Field(
        default=None,
        description="Kotak Neo TOTP secret",
    )
    KOTAK_MOBILE_NUMBER: Optional[str] = Field(
        default=None,
        description="Kotak Neo mobile number",
    )
    KOTAK_MPIN: Optional[str] = Field(
        default=None,
        description="Kotak Neo MPIN",
    )
    KOTAK_UCC: Optional[str] = Field(
        default=None,
        description="Kotak Neo UCC",
    )
    KOTAK_ENVIRONMENT: str = Field(
        default="prod",
        description="Kotak Neo environment: prod or sandbox",
    )

    # -------------------------------------------------------------------------
    # 6. xAI GROK (AI Brain - financial news analysis ONLY)
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
    # 7. URLS & CORS (CRITICAL FOR DEPLOYMENT)
    # -------------------------------------------------------------------------
    BACKEND_URL: str = Field(
        default="http://localhost:8000",
        description="Backend base URL",
    )
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        description="Frontend base URL",
    )
    ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="CORS allowed origins (comma-separated)",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse ALLOWED_ORIGINS into a list for CORSMiddleware."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    # -------------------------------------------------------------------------
    # 8. FEATURE GATES
    # -------------------------------------------------------------------------
    ENABLE_LIVE_TRADING: bool = Field(
        default=False,
        description="Enable live trading (DANGEROUS - only in production)",
    )
    ENABLE_PAPER_TRADING: bool = Field(
        default=True,
        description="Enable paper trading mode",
    )
    ENABLE_ALGO_EXECUTION: bool = Field(
        default=False,
        description="Enable algorithmic execution",
    )

    # -------------------------------------------------------------------------
    # 9. NOTIFICATIONS (OPTIONAL)
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
    # APPLICATION SETTINGS
    # -------------------------------------------------------------------------
    APP_HOST: str = Field(default="0.0.0.0", description="Application host")
    APP_PORT: int = Field(default=8000, description="Application port")

    # Timezone (IST only)
    TZ: str = Field(default="Asia/Kolkata", description="Application timezone")


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """Return the settings singleton."""
    return settings