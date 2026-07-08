"""Render the Phase C2 validation reel (walking-skeleton demo).

Builds the canonical 3-scene reel — blue "Title" → green "Subtitle" → red
"Call To Action" — renders it to a real MP4 with the FFmpeg backend, exports the
three aspect profiles, and probes every output for playability + correct
shape/duration.

    python -m reel_engine.scripts.render_demo
    python -m reel_engine.scripts.render_demo --renderer mock   # hermetic proxy

Exit codes:
    0  every output is readable with the expected resolution/aspect/duration
    1  ffmpeg unavailable for the ffmpeg renderer
    3  an output failed validation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.exporters import get_profile  # noqa: E402
from reel_engine.interfaces import RenderRequest  # noqa: E402
from reel_engine.timeline import build_demo_timeline, timeline_content_hash  # noqa: E402

DEMO_PROFILES = ("reel_9x16", "square_1x1", "landscape_16x9")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the C2 validation reel")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--scene-duration", type=float, default=2.0)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found on PATH. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    suffix = ".mp4" if args.renderer == "ffmpeg" else ".avi"
    cfg = ReelEngineConfig(render=RenderConfig(width=args.width, height=args.height,
                                               fps=args.fps, renderer=args.renderer))
    timeline = build_demo_timeline(width=args.width, height=args.height, fps=args.fps,
                                   duration_s=args.scene_duration)
    expected_duration = timeline.duration_s
    print(f"Timeline        : {timeline.n_scenes} scenes, {expected_duration:.1f}s, "
          f"{timeline.meta.aspect}, hash {timeline_content_hash(timeline)[:12]}")

    renderer = get_renderer(args.renderer, cfg)
    result = renderer.render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"demo_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))

    print(f"Renderer        : {result.renderer}")
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, "
          f"{result.duration_s:.2f}s, {result.render_time_s:.2f}s render)")

    # ---- validation (ffmpeg path: probe every output) ----
    problems: list[str] = []
    if args.renderer == "ffmpeg":
        master = probe_media(result.output_path)
        if not master.readable:
            problems.append("master not readable")
        if (master.width, master.height) != (args.width, args.height):
            problems.append(f"master resolution {master.width}x{master.height} "
                            f"!= {args.width}x{args.height}")
        if abs(master.duration_s - expected_duration) > 0.5:
            problems.append(f"master duration {master.duration_s} != ~{expected_duration}")
        for ex in result.exports:
            p = probe_media(ex.path)
            prof = get_profile(ex.profile)
            ok = p.readable and (p.width, p.height) == (prof.width, prof.height)
            print(f"  export {ex.profile:16} {p.width}x{p.height} {ex.aspect} "
                  f"{p.duration_s:.2f}s  {'OK' if ok else 'BAD'}")
            if not ok:
                problems.append(f"export {ex.profile} bad: {p.width}x{p.height}")
    else:
        for ex in result.exports:
            print(f"  export {ex.profile:16} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== C2 demo reel VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
