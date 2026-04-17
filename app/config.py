"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings.

    All settings can be overridden via environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # e.g. legacy IMAGE_DPI after native-PDF refactor
    )

    # Application
    app_name: str = "Personal Finance Intelligence"
    app_version: str = "2.0.0"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def coerce_debug_value(cls, value):
        """Allow DEBUG env values like WARN/INFO without raising validation errors."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug"}:
                return True
            if normalized in {
                "0",
                "false",
                "no",
                "off",
                "warn",
                "warning",
                "info",
                "error",
                "critical",
            }:
                return False
        return value

    # Database
    database_url: str = "sqlite+aiosqlite:///./statements.db"

    # File Upload
    upload_dir: str = "./static/uploads"
    max_file_size_mb: int = 10

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Claude AI (Anthropic)
    anthropic_api_key: Optional[str] = None

    # Model for statement extraction (vision).
    # "claude-haiku-4-5"   — fast, cheap (~15× cheaper than Sonnet), good for structured PDFs
    # "claude-sonnet-4-5"  — most accurate, higher cost
    extraction_model: str = "claude-haiku-4-5"

    # Max output tokens for extraction response.
    # Increase if you have very long statements (40+ transactions per page).
    extraction_max_tokens: int = 16000

    # Financial defaults
    default_currency: str = "BDT"

    # Authentication & Security
    jwt_secret_key: str = "your-secret-key-change-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    session_secret_key: str = "your-session-secret-change-in-production"
    session_timeout_minutes: int = 30  # Auto-logout after 30 minutes of inactivity

    # Google OAuth
    google_oauth_client_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_CLIENT_ID"),
    )
    google_oauth_client_secret: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_OAUTH_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET"),
    )
    google_oauth_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    # SMTP Email Configuration (for password reset)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from_email: str = "noreply@personalfinance.app"
    smtp_from_name: str = "Personal Finance Intelligence"

    # Frontend URL (for password reset links)
    frontend_url: str = "http://localhost:8000"
    password_reset_token_expire_minutes: int = 60  # 1 hour

    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes"""
        return self.max_file_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
