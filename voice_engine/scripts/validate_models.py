"""Validate installed models (run inside each model's venv).

    .venvs\\kokoro\\Scripts\\python.exe -m voice_engine.scripts.validate_models \
        --adapters kokoro --languages en hi

Writes JSON results + smoke-test WAVs to voice_engine/output/validation/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants import Language  # noqa: E402
from foundation.constants.paths import VOICE_ENGINE_DIR  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from voice_engine.adapters import ADAPTER_CLASSES, create_adapter  # noqa: E402
from voice_engine.models.validation import ModelValidator  # noqa: E402

VALIDATION_DIR = VOICE_ENGINE_DIR / "output" / "validation"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate installed voice models")
    parser.add_argument("--adapters", nargs="+", required=True, choices=sorted(ADAPTER_CLASSES))
    parser.add_argument("--languages", nargs="*", default=None,
                        choices=["en", "hi", "hi-en", "bn"])
    parser.add_argument("--reference-audio", default=None)
    parser.add_argument("--reference-text", default="", help="Transcript of the reference clip")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)

    configure_logging()
    languages = tuple(Language.from_code(c) for c in args.languages) if args.languages else None
    reference = Path(args.reference_audio) if args.reference_audio else None
    validator = ModelValidator(VALIDATION_DIR)

    all_valid = True
    for adapter_id in args.adapters:
        adapter = create_adapter(adapter_id, device=args.device)
        result = validator.validate(adapter, reference_audio=reference, languages=languages,
                                    reference_text=args.reference_text)
        path = validator.save(result)
        status = "VALID" if result.valid else "INVALID"
        print(f"[{status}] {adapter_id}: init={result.init_time_s}s "
              f"first={result.first_inference_s}s next={result.subsequent_inference_s}s "
              f"rss={result.peak_rss_mb}MB langs_ok={result.languages_ok} "
              f"({path.name})")
        if result.error:
            print(f"         error: {result.error[:300]}")
        all_valid &= result.valid
    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
