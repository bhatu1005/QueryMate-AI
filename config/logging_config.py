"""Central logging configuration for the application."""

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure a consistent console log format."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
