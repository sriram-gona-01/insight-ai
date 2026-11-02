"""Runtime settings, read from the environment or a local .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    database_url: str = "postgresql://insight:insight@localhost:5433/insight"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    embedding_dim: int = 384
    embedding_device: str = "auto"

    render_dpi: int = 150
    chunk_max_tokens: int = 480
    chunk_title_prefix: bool = True
    max_file_mb: int = 200
    ingest_stale_minutes: int = 30

    soffice_path: str = "soffice"
    soffice_timeout_seconds: int = 180
