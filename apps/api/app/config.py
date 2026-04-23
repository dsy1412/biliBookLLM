"""Application configuration via environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./data/bilibookllm.db"

    # --- LLM ---
    llm_api_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # --- Whisper (ASR) ---
    whisper_model: str = "base"
    whisper_compute_type: str = "int8"
    whisper_device: str = "auto"

    # --- Bilibili ---
    bilibili_sessdata: str = ""
    bilibili_cookies_file: str = ""

    # --- App ---
    debug: bool = True
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    job_timeout_seconds: int = 1800
    temp_dir: str = "./tmp"
    data_dir: str = "./data"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def temp_path(self) -> Path:
        p = Path(self.temp_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
