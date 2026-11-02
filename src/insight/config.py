"""Runtime settings, read from the environment or a local .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    data_dir: Path = Path("data")
    database_url: str = "postgresql://insight:insight@localhost:5433/insight"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_revision: str = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
    embedding_dim: int = 384
    embedding_device: str = "auto"
    embedding_query_instruction: str = "Represent this sentence for searching relevant passages: "

    render_dpi: int = 150
    chunk_max_tokens: int = 480
    chunk_title_prefix: bool = True
    max_file_mb: int = 200
    ingest_stale_minutes: int = 30

    soffice_path: str = "soffice"
    soffice_timeout_seconds: int = 180

    retrieval_overfetch: int = 5
    default_top_k: int = 3
    context_image_max_side: int = 1024

    llm_backend: str = "ollama"
    llm_model: str = "qwen3-vl:4b"
    ollama_url: str = "http://localhost:11434"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_temperature: float = 0.0
    llm_seed: int = 42
    llm_max_tokens: int = 512
    llm_context_tokens: int = 16384
    llm_timeout_seconds: int = 600
    llm_max_retries: int = 2

    api_url: str = "http://localhost:8000"
