"""Logging configuration using Loguru."""

import sys

from loguru import logger


def setup_logging() -> None:
    """Configure Loguru for the application."""
    # Remove default handler
    logger.remove()

    # Add console handler with structured format
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    logger.info("Logging initialized")
