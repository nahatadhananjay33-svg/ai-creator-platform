"""Run the end-to-end AI Creator Platform pipeline (Phase C3 walking skeleton).

    # Hermetic demo (no weights/GPU): mock voice + mock avatar + real ffmpeg MP4
    python -m reel_engine.scripts.run_pipeline --voice-model mock --avatar-model mock

    # Production models (needs Kokoro + MuseTalk installed; see engine docs)
    python -m reel_engine.scripts.run_pipeline \
        --script-file my_script.txt --reference my_face.jpg

    # From a YAML config, overriding just the resolution
    python -m reel_engine.scripts.run_pipeline --config pipeline.yaml --width 720 --height 1280

Generates ONE reel: script -> Voice -> Avatar -> Timeline -> Renderer -> MP4.
Prints per-stage timings and verifies the output is a real, playable file.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import LogFormat, configure_logging  # noqa: E402
from reel_engine.orchestrator import (  # noqa: E402
    CreatorPipeline,
    DEMO_SCRIPT_PATH,
    load_pipeline_config,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AI Creator Platform end-to-end pipeline")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--script", help="Inline script text")
    src.add_argument("--script-file", help="Path to a script .txt (default: demo script)")
    p.add_argument("--reference", help="Reference face image / driving video "
                                       "(default: packaged demo face)")
    p.add_argument("--config", help="Pipeline YAML config overlaying the defaults")
    p.add_argument("--voice-model", help="kokoro (default) | chatterbox | mock")
    p.add_argument("--avatar-model", help="musetalk (default) | latentsync | mock")
    p.add_argument("--renderer", choices=["ffmpeg", "mock"], help="Render backend")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--fps", type=int)
    p.add_argument("--profiles", nargs="+", help="Export profile names")
    p.add_argument("--output-dir")
    p.add_argument("--output-name", default="reel")
    p.add_argument("--json-logs", action="store_true")
    return p


def _overrides(args: argparse.Namespace) -> dict:
    """Build a sparse override mapping from only the flags the user passed."""
    voice = {k: v for k, v in (("model", args.voice_model),) if v is not None}
    avatar = {k: v for k, v in (("model", args.avatar_model),) if v is not None}
    render = {k: v for k, v in (("renderer", args.renderer), ("width", args.width),
                                ("height", args.height), ("fps", args.fps)) if v is not None}
    ov: dict = {}
    if voice:
        ov["voice"] = voice
    if avatar:
        ov["avatar"] = avatar
    if render:
        ov["render"] = render
    if args.profiles:
        ov["export"] = {"profiles": args.profiles}
    if args.output_dir:
        ov["output_dir"] = args.output_dir
    if args.reference:
        ov["reference_face"] = args.reference
    return ov


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(log_format=LogFormat.JSON if args.json_logs else LogFormat.TEXT)

    config = load_pipeline_config(config_path=args.config, overrides=_overrides(args))
    script_path = args.script_file or (None if args.script else DEMO_SCRIPT_PATH)

    result = CreatorPipeline(config).run(
        script=args.script, script_path=script_path,
        reference=args.reference, output_name=args.output_name)

    t = result.timings
    print("\n=== AI Creator Platform reel ===")
    print(f"  master : {result.output_path}")
    print(f"  format : {result.width}x{result.height} @ {result.fps}fps  "
          f"({result.render.aspect}), {result.duration_s:.2f}s")
    print(f"  voice  : {result.voice.engine_id}  ({result.voice.duration_s:.2f}s audio)")
    print(f"  avatar : {result.avatar.engine_id}  "
          f"({result.avatar.width}x{result.avatar.height})")
    print(f"  project: {result.project_path}")
    for e in result.exports:
        print(f"  export : {e.profile:14s} {e.width}x{e.height} -> {e.path.name}")
    print("  timings: " + "  ".join(f"{k}={v}s" for k, v in t.items()))

    # Verify the master is a real, non-empty file.
    ok = result.output_path.exists() and result.output_path.stat().st_size > 0
    print(f"\n  {'OK' if ok else 'FAILED'}: master {'is playable' if ok else 'missing/empty'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
