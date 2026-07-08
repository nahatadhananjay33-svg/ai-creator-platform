"""Regression tests for the permanent LatentSync GPU smoke test (Phase A4.7, M4).

These stay hermetic (no GPU / no model venv / no inference): they exercise the
prerequisite-checking and asset-resolution paths, which must fail loudly with
actionable messages and correct exit codes. The full GPU inference is validated
by running the script itself on a machine with the installed environment.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from avatar_engine.scripts import smoke_latentsync as smoke

SCRIPT_PATH = Path(smoke.__file__)


def test_smoke_script_exists():
    assert SCRIPT_PATH.exists() and SCRIPT_PATH.name == "smoke_latentsync.py"
    assert callable(smoke.main)


def test_help_exits_zero():
    # argparse --help proves the CLI is wired and the script executes.
    with pytest.raises(SystemExit) as exc:
        smoke.main(["--help"])
    assert exc.value.code == 0


def test_missing_install_returns_1_with_actionable_message(tmp_path, capsys):
    # Empty repo dir -> entrypoint + weights missing -> exit 1 BEFORE any venv
    # probe, with a message pointing at the installer.
    rc = smoke.main(["--repo-dir", str(tmp_path), "--output-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "not installed" in out
    assert "install_models --models latentsync" in out


def test_resolve_inputs_missing_assets_raises_code_2(tmp_path):
    with pytest.raises(smoke.SmokeError) as exc:
        smoke.resolve_inputs(tmp_path, 1.0, tmp_path / "work")
    assert exc.value.code == 2
    assert "demo assets not found" in str(exc.value)


def test_resolve_inputs_trims_audio_when_present(tmp_path):
    # Fabricate the two demo assets so resolve_inputs succeeds and trims audio.
    sf = pytest.importorskip("soundfile")
    import numpy as np

    video = tmp_path / smoke._DEMO_VIDEO
    audio = tmp_path / smoke._DEMO_AUDIO
    video.parent.mkdir(parents=True, exist_ok=True)
    audio.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(b"\x00\x00\x00\x18ftypmp42")  # header is enough; not decoded here
    sr = 16000
    sf.write(str(audio), np.zeros(sr * 4, dtype="float32"), sr)  # 4s clip

    resolved_video, trimmed = smoke.resolve_inputs(tmp_path, 1.0, tmp_path / "work")
    assert resolved_video == video
    # Trimmed to ~1s (< the 4s source), written into the work dir.
    assert trimmed != audio and trimmed.exists()
    assert sf.info(str(trimmed)).duration == pytest.approx(1.0, abs=0.05)


def test_prepare_audio_falls_back_to_source_on_error(tmp_path):
    # A non-audio file can't be trimmed -> best-effort fallback returns the source.
    bogus = tmp_path / "not_audio.wav"
    bogus.write_bytes(b"not a real wav")
    assert smoke._prepare_audio(bogus, 1.0, tmp_path / "work") == bogus
