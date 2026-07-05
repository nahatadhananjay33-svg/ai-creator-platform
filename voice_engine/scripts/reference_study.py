"""Run the reference-audio duration study (engine acceptance is stdlib-only,
so this runs on the host interpreter).

    python -m voice_engine.scripts.reference_study
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import VOICE_ENGINE_DIR  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from voice_engine.adapters import ADAPTER_CLASSES  # noqa: E402
from voice_engine.cloning.reference_validation import (  # noqa: E402
    STANDARD_DURATIONS_S,
    ReferenceValidationStudy,
    save_study,
)

CLIPS_DIR = VOICE_ENGINE_DIR / "datasets" / "reference_audio" / "synthetic"
OUTPUT_DIR = VOICE_ENGINE_DIR / "output" / "validation"


def main() -> int:
    configure_logging()
    clips = {
        d: CLIPS_DIR / f"synthetic_en_{d}s.wav"
        for d in STANDARD_DURATIONS_S
        if (CLIPS_DIR / f"synthetic_en_{d}s.wav").exists()
    }
    if not clips:
        print(f"No clips found in {CLIPS_DIR}; run generate_reference_clips first.")
        return 1

    adapters = [cls(device="cpu") for cls in ADAPTER_CLASSES.values()]
    study = ReferenceValidationStudy(adapters)
    result = study.run(clips)
    path = save_study(result, OUTPUT_DIR)

    print(f"\nClips analyzed: {len(result.clips)}")
    for clip in result.clips:
        print(f"  {Path(clip.path).name}: {clip.duration_s}s @ {clip.sample_rate}Hz, "
              f"speech {clip.speech_duration_s}s, silence {clip.silence_ratio:.0%}, "
              f"clipping {clip.clipping_ratio:.2%}"
              + (f" — WARNINGS: {'; '.join(clip.warnings)}" if clip.warnings else ""))
    print("\nPer-engine recommendations:")
    for engine, rec in sorted(result.recommendations.items()):
        print(f"  {engine}: recommended {rec['recommended_duration_s']}s "
              f"(min {rec['engine_minimum_s']}s; accepted {rec['accepted_durations_s']})")
    print(f"\nSaved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
