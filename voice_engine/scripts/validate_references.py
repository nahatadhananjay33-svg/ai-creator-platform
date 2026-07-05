"""Validate reference audio clips for voice cloning.

Checks every WAV in voice_engine/datasets/reference_audio/ against the
strictest adapter requirements and prints a per-file report.

    python -m voice_engine.scripts.validate_references
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from voice_engine.adapters.mock import MockVoiceAdapter  # noqa: E402

REFERENCE_DIR = Path(__file__).resolve().parents[1] / "datasets" / "reference_audio"


def main() -> int:
    configure_logging()
    validator = MockVoiceAdapter()  # base-class rules; engine minimums differ
    wavs = sorted(REFERENCE_DIR.glob("*.wav"))
    if not wavs:
        print(f"No WAV files in {REFERENCE_DIR} — see its README.md for the required set.")
        return 1
    failures = 0
    for wav in wavs:
        problems = validator.validate_reference(wav)
        status = "OK " if not problems else "BAD"
        print(f"[{status}] {wav.name}" + (f" — {'; '.join(problems)}" if problems else ""))
        failures += bool(problems)
    print(f"\n{len(wavs) - failures}/{len(wavs)} reference clips valid.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
