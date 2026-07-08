"""Regression tests for the permanent Chatterbox GPU smoke test (Phase B2.2).

Hermetic: no chatterbox install, no GPU, no synthesis. Exercises the
prerequisite-check and CLI plumbing paths, which must fail loudly with an
actionable message + the right exit code, plus the self-contained synthetic
reference generator (which must produce a WAV the adapter's
``validate_reference`` accepts). The real GPU synthesis is validated by running
the script in the chatterbox venv on a T4.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.shared_utils import read_wav
from voice_engine.adapters.chatterbox import ChatterboxAdapter
from voice_engine.scripts import smoke_chatterbox as smoke

SCRIPT_PATH = Path(smoke.__file__)


def test_smoke_script_exists():
    assert SCRIPT_PATH.exists() and SCRIPT_PATH.name == "smoke_chatterbox.py"
    assert callable(smoke.main)


def test_help_exits_zero():
    with pytest.raises(SystemExit) as exc:
        smoke.main(["--help"])
    assert exc.value.code == 0


def test_demo_text_covers_both_languages():
    assert Language.ENGLISH in smoke._DEMO_TEXT
    assert Language.HINDI in smoke._DEMO_TEXT
    # Hindi line is Devanagari (multilingual 'hi' path), not romanized.
    assert any("ऀ" <= ch <= "ॿ" for ch in smoke._DEMO_TEXT[Language.HINDI])


def test_missing_install_returns_1_with_actionable_message(monkeypatch, capsys, tmp_path):
    # Force "not installed" regardless of the running env, so this stays hermetic.
    monkeypatch.setattr(smoke.ChatterboxAdapter, "is_available", lambda self: False)
    rc = smoke.main(["--output-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not installed" in out
    assert "install_models --models chatterbox" in out


def test_synthetic_reference_is_accepted_by_adapter(tmp_path):
    # The synthetic reference must satisfy validate_reference (>= 7 s, not
    # clipped, not near-silent) — otherwise the smoke test can never build a
    # voice profile even with chatterbox installed.
    ref = smoke._synthetic_reference(tmp_path / "ref.wav")
    wav = read_wav(ref)
    assert wav.duration_s >= 7.0
    problems = ChatterboxAdapter(device="cpu").validate_reference(ref)
    assert problems == [], problems
