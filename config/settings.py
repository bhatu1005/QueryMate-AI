"""Environment-backed application settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "QueryMate AI"
    app_env: str = "development"
    log_level: str = "INFO"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.2:1b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    ollama_timeout_seconds: float = Field(default=120.0, gt=0.0)

    mysql_host: str = "localhost"
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_database: str = "company_db"
    mysql_user: str = "querymate_readonly"
    mysql_password: SecretStr = SecretStr("")
    mysql_connect_timeout: int = Field(default=10, ge=1)
    sql_max_rows: int = Field(default=500, ge=1)
    sql_query_timeout_seconds: int = Field(default=15, ge=1)

    upload_dir: Path = Path("data/uploads")
    chroma_persist_dir: Path = Path("data/chroma_db")
    max_upload_size_mb: int = Field(default=25, ge=1)

    chunk_size: int = Field(default=1000, ge=1)
    chunk_overlap: int = Field(default=150, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1)
    retrieval_min_relevance_score: float = Field(default=0.15, ge=0.0, le=1.0)
    graph_recursion_limit: int = Field(default=12, ge=2, le=50)
    agent_max_retries: int = Field(default=1, ge=0, le=3)

    mcp_server_command: str = "python"
    mcp_server_args: str = "mcp_server/server.py"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings for the current process."""
    return Settings()
