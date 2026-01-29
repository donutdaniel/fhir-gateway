"""
Structured logging configuration for FHIR Gateway.

This module provides structured JSON logging using structlog for
production-ready logging with request correlation IDs.
"""

import logging
import sys
import uuid
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

import structlog


@dataclass
class LoggingConfig:
    """Logging configuration."""

    suppressed_loggers: dict[str, str] = field(
        default_factory=lambda: {
            "httpx": "WARNING",
            "httpcore": "WARNING",
            "aiohttp": "WARNING",
            "urllib3": "WARNING",
            "asyncio": "WARNING",
            "uvicorn.access": "WARNING",
        }
    )
    request_id_length: int = 8
    colors: bool = True


# Default logging configuration
_logging_config = LoggingConfig()


# Context variable for request correlation ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set a new request ID in context. Generates one if not provided."""
    new_id = request_id or str(uuid.uuid4())[: _logging_config.request_id_length]
    request_id_var.set(new_id)
    return new_id


def add_request_id(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Structlog processor to add request ID to log events."""
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARN, ERROR)
        json_format: If True, output JSON logs; otherwise, use console format
    """
    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Common processors for all outputs
    shared_processors: list[Callable] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_request_id,
    ]

    if json_format:
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=_logging_config.colors),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Suppress noisy loggers
    for logger_name, logger_level in _logging_config.suppressed_loggers.items():
        suppressed_level = getattr(logging, logger_level.upper(), logging.WARNING)
        logging.getLogger(logger_name).setLevel(suppressed_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
