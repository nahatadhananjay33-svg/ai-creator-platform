"""Validate the avatar benchmark's driving audio (Phase A3.8.5).

Classifies every scenario's driving WAV as real speech vs placeholder tone /
silent / corrupted / missing, and writes:

    avatar_engine/output/validation/audio_validation_report.md
    avatar_engine/output/validation/audio_validation_report.json

Usage:
    python -m avatar_engine.scripts.validate_audio
    python -m avatar_engine.scripts.validate_audio --assets-dir path/to/wavs

Exit code is non-zero if any scenario's audio is not real speech, so this can
gate a pipeline before avatar generation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from voice_engine.metrics import validate_wav, write_audio_validation_report  # noqa: E402
from avatar_engine.datasets import AvatarDatasetManager  # noqa: E402

VALIDATION_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate avatar driving audio")
    parser.add_argument("--assets-dir", default=None, help="Override the dataset assets dir")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args(argv)

    configure_logging()
    manager = AvatarDatasetManager(assets_dir=Path(args.assets_dir) if args.assets_dir else None)
    dataset = manager.load()

    validations, labels = [], {}
    for scenario in dataset.scenarios:
        assets = manager.resolve_assets(scenario)
        v = validate_wav(assets.driving_audio, expected_duration_s=scenario.target_duration_s)
        validations.append(v)
        labels[v.path] = scenario.script_text
        mark = "SPEECH " if v.is_speech else ("PLACEHOLDER" if v.is_placeholder else "INVALID")
        print(f"[{mark:11}] {scenario.scenario_id:22} {v.audio_class:9} {v.reason}")

    out_dir = Path(args.output_dir) if args.output_dir else VALIDATION_DIR
    reports = write_audio_validation_report(validations, out_dir, label_by_path=labels)
    print("\nReports:")
    for kind, path in reports.items():
        print(f"  {kind}: {path}")
    valid = sum(v.valid for v in validations)
    print(f"\n{valid}/{len(validations)} scenarios have real speech.")
    return 0 if valid == len(validations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
