"""Validate installed avatar models (run inside each model's venv).

    .venvs\\sadtalker\\Scripts\\python.exe -m avatar_engine.scripts.validate_models \
        --adapters sadtalker --source-image <img> --driving-audio <wav>

Writes JSON results + smoke videos to avatar_engine/output/validation/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from avatar_engine.models import ADAPTER_CLASSES, create_adapter  # noqa: E402
from avatar_engine.models.validation import AvatarModelValidator  # noqa: E402

VALIDATION_DIR = Path(__file__).resolve().parents[1] / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate installed avatar models")
    parser.add_argument("--adapters", nargs="+", required=True, choices=sorted(ADAPTER_CLASSES))
    parser.add_argument("--source-image", default=None)
    parser.add_argument("--driving-audio", default=None)
    parser.add_argument("--driving-video", default=None)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)

    configure_logging()
    validator = AvatarModelValidator(VALIDATION_DIR)
    all_valid = True
    for adapter_id in args.adapters:
        adapter = create_adapter(adapter_id, device=args.device)
        result = validator.validate(
            adapter,
            source_image=Path(args.source_image) if args.source_image else None,
            driving_audio=Path(args.driving_audio) if args.driving_audio else None,
            driving_video=Path(args.driving_video) if args.driving_video else None,
        )
        path = validator.save(result)
        status = "VALID" if result.valid else "INVALID"
        print(f"[{status}] {adapter_id}: load={result.load_time_s}s "
              f"first_gen={result.first_generation_s}s rtf={result.real_time_factor} "
              f"video={result.video_resolution}@{result.video_fps}fps "
              f"rss={result.peak_rss_mb}MB ({path.name})")
        if result.error:
            print(f"          error: {result.error[:300]}")
        all_valid &= result.valid
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
