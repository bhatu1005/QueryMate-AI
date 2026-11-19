"""Reusable LangChain embeddings client for local Ollama."""

from functools import lru_cache

from langchain_ollama import OllamaEmbeddings

from config.settings import Settings, get_settings


@lru_cache(maxsize=8)
def _build_embeddings(base_url: str, model: str, timeout_seconds: float) -> OllamaEmbeddings:
    """Construct and cache an Ollama embeddings client."""
    return OllamaEmbeddings(
        model=model,
        base_url=base_url,
        client_kwargs={"timeout": timeout_seconds},
        validate_model_on_init=True,
    )


def get_embeddings(settings: Settings | None = None) -> OllamaEmbeddings:
    """Return the reusable local embedding client configured by environment settings."""
    active = settings or get_settings()
    return _build_embeddings(
        active.ollama_base_url,
        active.ollama_embedding_model,
        active.ollama_timeout_seconds,
    )
