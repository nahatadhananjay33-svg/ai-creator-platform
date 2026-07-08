"""Regression tests for the permanent Kokoro CPU smoke test (Phase B2.1).

Hermetic: no kokoro install, no synthesis. Exercises the prerequisite-check and
CLI plumbing paths, which must fail loudly with an actionable message + the
right exit code. The real CPU synthesis is validated by running the script in
the kokoro venv.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from voice_engine.scripts import smoke_kokoro as smoke

SCRIPT_PATH = Path(smoke.__file__)


def test_smoke_script_exists():
    assert SCRIPT_PATH.exists() and SCRIPT_PATH.name == "smoke_kokoro.py"
    assert callable(smoke.main)


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        smoke.main(["--help"])
    assert exc.value.code == 0


def test_demo_text_covers_both_languages():
    assert Language.ENGLISH in smoke._DEMO_TEXT
    assert Language.HINDI in smoke._DEMO_TEXT
    # Hindi line is Devanagari (Kokoro 'h' G2P), not romanized.
    assert any("ऀ" <= ch <= "ॿ" for ch in smoke._DEMO_TEXT[Language.HINDI])


def test_missing_install_returns_1_with_actionable_message(monkeypatch, capsys, tmp_path):
    # Force "not installed" regardless of the running env, so this stays hermetic.
    monkeypatch.setattr(smoke.KokoroAdapter, "is_available", lambda self: False)
    rc = smoke.main(["--output-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not installed" in out
    assert "install_models --models kokoro" in out
