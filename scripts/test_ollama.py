"""Smoke test the configured local Ollama chat and embedding models."""

import logging
import sys

from config.logging_config import configure_logging
from config.settings import get_settings
from llm.embeddings import get_embeddings
from llm.ollama_client import check_ollama_health, get_chat_model, require_ollama


def main() -> int:
    """Ask a test question and print the embedding vector dimensions."""
    settings = get_settings()
    configure_logging(settings.log_level)
    print("Ollama health:", check_ollama_health(settings))
    try:
        require_ollama(settings)
        response = get_chat_model(settings).invoke("In one sentence, what is SQL?")
        print("Llama response:")
        print(response.content)
        vector = get_embeddings(settings).embed_query("QueryMate local embedding smoke test.")
        print(f"Embedding dimensions: {len(vector)}")
    except Exception as exc:
        logging.getLogger(__name__).error("Ollama smoke test failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
