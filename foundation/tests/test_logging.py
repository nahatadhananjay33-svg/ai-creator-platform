"""Tests for foundation.logging."""
from __future__ import annotations

import io
import json

from foundation.logging import LogFormat, configure_logging, get_logger


def test_json_format_emits_valid_json() -> None:
    stream = io.StringIO()
    configure_logging(level="INFO", log_format=LogFormat.JSON, stream=stream)
    logger = get_logger("test.json")
    logger.info("hello", extra={"context": {"model": "f5-tts", "rtf": 0.2}})
    record = json.loads(stream.getvalue().strip())
    assert record["message"] == "hello"
    assert record["level"] == "INFO"
    assert record["context"] == {"model": "f5-tts", "rtf": 0.2}
    assert record["logger"].startswith("aicp.")


def test_text_format_includes_context() -> None:
    stream = io.StringIO()
    configure_logging(level="INFO", log_format=LogFormat.TEXT, stream=stream)
    get_logger("test.text").info("synth done", extra={"context": {"lang": "hi"}})
    out = stream.getvalue()
    assert "synth done" in out
    assert "lang=hi" in out


def test_get_logger_namespacing() -> None:
    assert get_logger("voice_engine").name == "aicp.voice_engine"
    assert get_logger("aicp.voice_engine").name == "aicp.voice_engine"
