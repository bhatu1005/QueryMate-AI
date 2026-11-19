"""Local dependency health checks for the Streamlit sidebar."""

import logging

from config.settings import Settings, get_settings
from database.connection import connect_readonly
from llm.ollama_client import check_ollama_health

logger = logging.getLogger(__name__)


def check_database(settings: Settings | None = None) -> tuple[bool, str]:
    """Check MySQL connectivity with a harmless constant SELECT."""
    connection = None
    try:
        connection = connect_readonly(settings or get_settings())
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return True, "Connected"
    except Exception:
        logger.exception("Database health check failed")
        return False, "Unavailable"
    finally:
        if connection is not None:
            connection.close()


def check_models(settings: Settings | None = None) -> tuple[bool, str]:
    """Check Ollama reachability and configured local model availability."""
    report = check_ollama_health(settings)
    if not report["server_connected"]:
        return False, "Ollama offline"
    if report["chat_model_available"] and report["embedding_model_available"]:
        return True, "Models ready"
    missing = []
    if not report["chat_model_available"]:
        missing.append(str(report["chat_model"]))
    if not report["embedding_model_available"]:
        missing.append(str(report["embedding_model"]))
    return False, "Missing " + ", ".join(missing)
