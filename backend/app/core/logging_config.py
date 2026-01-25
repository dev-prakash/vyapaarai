"""
Centralized Logging Configuration for VyaparAI

Provides:
- Consistent log format across all modules
- Structured JSON logging for production
- Request ID injection into log records
- Log level configuration via environment variables

Usage:
    from app.core.logging_config import setup_logging, get_logger

    # At application startup
    setup_logging()

    # In modules
    logger = get_logger(__name__)
    logger.info("Message", extra={"request_id": "req_123"})
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    "setup_logging",
    "get_logger",
    "set_request_id",
    "get_request_id",
    "RequestIdFilter",
    "JsonFormatter",
    "LOG_LEVELS",
]

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Log level configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG" if not IS_PRODUCTION else "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "json" if IS_PRODUCTION else "text")

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def set_request_id(request_id: str) -> None:
    """Set the current request ID for logging context"""
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """Get the current request ID from logging context"""
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """
    Logging filter that adds request_id to all log records.
    Uses context variable for thread-safe request ID tracking.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging in production.
    Outputs logs in a format suitable for log aggregation systems.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "request_id"
            ):
                if not key.startswith("_"):
                    log_data[key] = value

        return json.dumps(log_data, default=str)


class StandardFormatter(logging.Formatter):
    """
    Standard text formatter with request ID for development.
    """

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s [%(levelname)8s] [%(request_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logging(
    level: Optional[str] = None,
    log_format: Optional[str] = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "text")
    """
    level = level or LOG_LEVEL
    log_format = log_format or LOG_FORMAT

    # Get the root logger
    root_logger = logging.getLogger()

    # Clear existing handlers
    root_logger.handlers.clear()

    # Set log level
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Add request ID filter
    handler.addFilter(RequestIdFilter())

    # Set formatter based on format type
    if log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(StandardFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info(
        f"Logging configured: level={level}, format={log_format}, env={ENVIRONMENT}"
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Convenience function for logging with extra context
def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **extra: Any
) -> None:
    """
    Log a message with extra context fields.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **extra: Additional context fields
    """
    logger.log(level, message, extra=extra)
