"""
Application configuration using Pydantic Settings.
Loads configuration from environment variables and .env file.
"""
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

    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes"""
        return self.max_file_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
