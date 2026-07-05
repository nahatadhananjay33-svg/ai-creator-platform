"""Structured logging built on the stdlib ``logging`` module.

Design:
- One root logger namespace: ``aicp`` (e.g. ``aicp.voice_engine.benchmark``).
- Two output formats: human-readable text (default) and JSON lines for
  machine ingestion (production services, benchmark run logs).
- Loggers accept structured context via the ``extra={"context": {...}}``
  convention; the JSON formatter merges it into the emitted record.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any

ROOT_LOGGER_NAME = "aicp"


class LogFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload["context"] = context
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Readable single-line format with optional context suffix."""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            pairs = " ".join(f"{k}={v}" for k, v in context.items())
            return f"{base} | {pairs}"
        return base


def configure_logging(
    level: int | str = logging.INFO,
    log_format: LogFormat = LogFormat.TEXT,
    stream: Any = None,
) -> logging.Logger:
    """Configure the platform root logger. Idempotent.

    Args:
        level: Log level for the platform namespace.
        log_format: TEXT for development, JSON for production/benchmark runs.
        stream: Output stream (defaults to stderr).
    """
    root = logging.getLogger(ROOT_LOGGER_NAME)
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        JsonFormatter() if log_format is LogFormat.JSON else TextFormatter()
    )
    root.addHandler(handler)
    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the platform namespace.

    ``get_logger("voice_engine.benchmark")`` -> logger ``aicp.voice_engine.benchmark``.
    """
    if name.startswith(ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
