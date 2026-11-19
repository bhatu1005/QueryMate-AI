"""Reusable LangChain chat model and health checks for local Ollama."""

from functools import lru_cache
import logging
from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import ChatOllama

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class OllamaConnectionError(RuntimeError):
    """Raised when the local Ollama service or required models are unavailable."""


@lru_cache(maxsize=8)
def _build_chat_model(base_url: str, model: str, temperature: float, timeout_seconds: float) -> ChatOllama:
    """Construct and cache a LangChain ChatOllama instance."""
    return ChatOllama(model=model, base_url=base_url, temperature=temperature, timeout=timeout_seconds)


def get_chat_model(settings: Settings | None = None) -> ChatOllama:
    """Return the reusable local chat model configured by environment settings."""
    active = settings or get_settings()
    return _build_chat_model(
        active.ollama_base_url,
        active.ollama_chat_model,
        active.ollama_temperature,
        active.ollama_timeout_seconds,
    )


def _model_is_installed(model_name: str, installed_names: set[str | None]) -> bool:
    """Match model names with or without an explicit `:latest` tag."""
    names = {name for name in installed_names if name}
    return model_name in names or (":" not in model_name and f"{model_name}:latest" in names)


def check_ollama_health(settings: Settings | None = None) -> dict[str, Any]:
    """Check Ollama connectivity and availability of configured model tags."""
    active = settings or get_settings()
    report: dict[str, Any] = {
        "server_connected": False,
        "chat_model": active.ollama_chat_model,
        "chat_model_available": False,
        "embedding_model": active.ollama_embedding_model,
        "embedding_model_available": False,
        "error": None,
    }
    try:
        with httpx.Client(timeout=active.ollama_timeout_seconds) as client:
            response = client.get(f"{active.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()
        report["server_connected"] = True
        installed = {
            item.get("name") or item.get("model")
            for item in payload.get("models", [])
            if isinstance(item, dict)
        }
        report["chat_model_available"] = _model_is_installed(active.ollama_chat_model, installed)
        report["embedding_model_available"] = _model_is_installed(active.ollama_embedding_model, installed)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        report["error"] = f"Cannot check Ollama at {active.ollama_base_url}: {exc}"
        logger.warning("Ollama health check failed: %s", exc)
    return report


def require_ollama(settings: Settings | None = None) -> dict[str, Any]:
    """Raise an actionable connection error if the server or models are missing."""
    report = check_ollama_health(settings)
    if not report["server_connected"]:
        raise OllamaConnectionError(report["error"] or "Ollama server is unavailable.")
    missing = [
        name
        for name, key in ((report["chat_model"], "chat_model_available"),
                          (report["embedding_model"], "embedding_model_available"))
        if not report[key]
    ]
    if missing:
        raise OllamaConnectionError(
            "Ollama is reachable, but required model(s) are not installed: " + ", ".join(missing)
            + ". Pull them with `ollama pull <model>`."
        )
    return report
