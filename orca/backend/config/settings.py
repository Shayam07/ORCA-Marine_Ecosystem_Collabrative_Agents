"""ORCA Configuration Settings."""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find .env relative to project root (orca/)
_backend_dir = Path(__file__).resolve().parent.parent  # orca/backend
_project_root = _backend_dir.parent  # orca/
_env_file = str(_project_root / ".env")


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "ORCA — Marine Ecosystem Intelligence"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://orca:orca@localhost:5432/orca"
    DATABASE_URL_SYNC: str = "postgresql://orca:orca@localhost:5432/orca"

    # Supabase Auth & JWT Validation
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM — Gemini or Groq is enough for general Q&A
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "qwen/qwen3.6-27b"
    LLM_BASE_URL: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # ISRO / MOSDAC
    MOSDAC_BASE_URL: Optional[str] = None
    MOSDAC_API_KEY: Optional[str] = None
    MOSDAC_USERNAME: Optional[str] = None
    MOSDAC_PASSWORD: Optional[str] = None

    # Copernicus Marine
    COPERNICUS_USERNAME: Optional[str] = None
    COPERNICUS_PASSWORD: Optional[str] = None

    # NASA
    NASA_API_KEY: Optional[str] = None
    NASA_USERNAME: Optional[str] = None
    NASA_PASSWORD: Optional[str] = None

    # NOAA
    NOAA_API_KEY: Optional[str] = None

    # Fishing Activity
    FISHING_API_KEY: Optional[str] = None

    # Map
    MAPTILER_API_KEY: Optional[str] = None

    # Data mode
    # Production default: never present generated observations as current data.
    # Demo is available only through an explicit request from the UI/developer.
    DATA_MODE: str = "live"  # "live", "cached", "demo"

    # Server host binding
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "https://localhost",
        "capacitor://localhost",
        "http://10.0.2.2",
        "http://10.0.2.2:8000",
        "http://10.0.2.2:5173",
        "http://192.168.1.48",
        "http://192.168.1.48:8000",
        "http://192.168.1.48:5173",
    ]

    # Cache TTL (seconds)
    CACHE_TTL: int = 3600

    # API rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60


settings = Settings()
