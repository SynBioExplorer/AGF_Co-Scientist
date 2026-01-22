"""Structured logging configuration"""

import structlog
import logging


def setup_logging(level: str = "INFO"):
    """Configure structured logging with JSON output"""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper())
    )

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
