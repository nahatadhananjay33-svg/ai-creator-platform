"""Intelligent Asset Retrieval validation demo (Phase C9).

Proves the deterministic provider pipeline end to end:

    script -> Scene Planner (AssetSlots) -> Asset Resolver (local catalog)
           -> AssetTrack -> Timeline -> Renderer -> playable MP4

The Scene Planner emits typed :class:`AssetSlot` *requests*; this demo satisfies
EVERY slot automatically from a local catalog — no manual asset wiring, no
downloads, no AI. The catalog is a set of deterministic placeholder images (an
"ideal" portrait match per slot plus wrong-aspect / off-topic distractors), so
ranking has to actually choose, and the choice is reproducible.

    python -m asset_engine.scripts.render_resolver_demo                  # ffmpeg MP4
    python -m asset_engine.scripts.render_resolver_demo --renderer mock  # hermetic proxy

Verification (backend-independent): every required slot is satisfied (NO missing
assets — strict mode), each resolved clip's window matches its slot (correct
timing), each clip's layout matches its slot (correct layouts), the ideal
candidate outranks the distractors, and the Timeline validates. The master +
exports are then probed for playability (correct rendering).

Exit codes:
    0  every slot resolved + timing/layouts correct + outputs playable
    1  ffmpeg unavailable for the ffmpeg renderer
    3  a resolution/timing/layout check or an output failed
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402

from asset_engine import AssetEngine  # noqa: E402
from asset_engine.providers.placeholder import generate_image  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.render.assets import resolve_assets  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402
from scene_engine import SceneEngine  # noqa: E402

DEMO_PROFILES = ("reel_9x16", "square_1x1")
_EXPORT_DIMS = {"reel_9x16": (1080, 1920), "square_1x1": (1080, 1080)}
#: A ~40s script that makes the planner request a chart, an image insert, and a
#: comparison (two image halves) — an image-family retrieval spread.
DEMO_SCRIPT = (
    "Ever wondered why some rockets look so different from others?\n\n"
    "The data shows that over 90 percent of a rocket is fuel at launch.\n\n"
    "Take a look at this photo of a rocket climbing through the clouds.\n\n"
    "Compared to a jet engine, a rocket carries its own oxygen, whereas a jet "
    "breathes the air around it.\n\n"
    "So if this was useful, subscribe and follow for more space science.\n\n"
)


def _build_catalog(slots, root: Path) -> Path:
    """Generate a deterministic local library that can satisfy every slot.

    For each slot's kind we write, under ``{kind}s/``: an IDEAL portrait match
    (tagged from the slot hint, 1080x1920 so it fits a 9:16 region), a LANDSCAPE
    distractor (same tags, wrong aspect), and an OFF-TOPIC distractor (portrait,
    unrelated tags). Ranking must prefer the ideal on aspect + tag overlap."""
    from asset_engine.catalog.index import tokenize_tags
    for slot in slots:
        kind = slot.kind
        tags = tokenize_tags(slot.hint)[:3]
        stem = "_".join(tags) if tags else "topic"
        d = root / f"{kind}s"
        generate_image(d / f"ideal_{stem}.png", width=1080, height=1920)
        generate_image(d / f"landscape_{stem}.png", width=1920, height=1080)
        generate_image(d / f"offtopic_misc_stock_generic.png", width=1080, height=1920)
    return root


def _verify(storyboard, track, resolutions, frame) -> dict:
    """Backend-independent resolution / timing / layout checks."""
    slots = list(storyboard.all_asset_slots)
    by_id = {c.clip_id: c for c in track.clips}
    checks: dict = {}

    checks["slots requested > 0"] = len(slots) > 0
    checks["every required slot satisfied (no missing assets)"] = all(
        r.satisfied for r in resolutions)
    checks["one clip per slot"] = len(track.clips) == len(slots)

    timing_ok = layout_ok = ideal_ok = True
    for slot in slots:
        clip = by_id.get(slot.slot_id)
        if clip is None:
            timing_ok = layout_ok = False
            continue
        if abs(clip.start_s - slot.start_s) > 1e-6 or abs(clip.end_s - slot.end_s) > 1e-6:
            timing_ok = False
        if clip.layout.kind != slot.layout:
            layout_ok = False
    checks["correct timing (clip window == slot window)"] = timing_ok
    checks["correct layouts (clip layout == slot layout)"] = layout_ok

    # ranking actually chose the ideal portrait match over the distractors
    for r in resolutions:
        if r.satisfied and "ideal_" not in Path(r.candidate.path).name:
            ideal_ok = False
    checks["ranking chose the ideal candidate over distractors"] = ideal_ok
    # no overlapping side on comparison pairs (sided layouts alternate halves)
    sided = [c for c in track.clips if c.layout.kind in ("side_by_side", "split_screen")]
    if len(sided) >= 2:
        checks["sided layouts alternate halves"] = len({c.layout.side for c in sided}) > 1
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Intelligent Asset Retrieval demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "resolver_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps = args.width, args.height, args.fps

    # 1) PLAN: script -> Storyboard (with AssetSlot requests).
    engine = SceneEngine()
    storyboard = engine.plan(DEMO_SCRIPT, title="Asset Resolver demo")
    slots = list(storyboard.all_asset_slots)
    print(f"Storyboard      : {storyboard.n_scenes} scenes, {len(slots)} asset slots")
    for s in slots:
        print(f"  slot {s.slot_id} kind={s.kind:6} layout={s.layout:18} "
              f"[{s.start_s:.1f}-{s.end_s:.1f}]s  hint={s.hint!r}")

    # 2) CATALOG: a deterministic local library covering every slot kind.
    library = _build_catalog(slots, out_dir / "library")

    # 3) RESOLVE: satisfy EVERY slot from the catalog (strict -> no missing).
    asset_engine = AssetEngine()
    track, resolutions = asset_engine.resolve_slots(
        slots, frame_width=w, frame_height=h, library_dir=library, strict=True)
    print(f"Resolved        : {track.n_clips}/{len(slots)} slots from "
          f"catalog ({AssetEngine().build_resolver(library_dir=library).manager.names})")
    for r in resolutions:
        print(f"  {r.slot_id} -> {Path(r.candidate.path).name:32} "
              f"score={r.score:.2f} (from {len(r.ranked)} candidates)")

    # 4) TIMELINE: scenes + captions (Scene Engine) + the resolved AssetTrack.
    timeline = engine.build_timeline(storyboard, width=w, height=h, fps=fps)
    timeline = dataclasses.replace(timeline, asset_tracks=(track,))
    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")

    # ---- backend-independent verification ----
    problems: list[str] = []
    checks = _verify(storyboard, track, resolutions, (w, h))
    # determinism: resolving again picks the identical assets.
    track2, _ = asset_engine.resolve_slots(slots, frame_width=w, frame_height=h,
                                           library_dir=library, strict=True)
    checks["deterministic resolution (same assets)"] = (
        [c.source.uri for c in track.clips] == [c.source.uri for c in track2.clips])
    checks["timeline validates"] = validate_timeline(timeline) == []
    print("Resolution checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"check failed: {name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    # 5) RENDER: master (assets composited) + exports.
    render_cfg = ReelEngineConfig(render=RenderConfig(
        width=w, height=h, fps=fps, renderer=args.renderer))
    result = get_renderer(args.renderer, render_cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"resolver_reel{'.mp4' if args.renderer=='ffmpeg' else '.avi'}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height}")
        if not result.metadata.get("assets"):
            problems.append("resolved assets were not composited into the master")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable or (pe.width, pe.height) != _EXPORT_DIMS[ex.profile]:
                problems.append(f"export {ex.profile} bad: {pe.width}x{pe.height}")
    else:
        from foundation.shared_utils.video_io import read_raw_avi
        if read_raw_avi(result.output_path).n_frames <= 0:
            problems.append("mock master has no frames")
        if len(resolve_assets(timeline)) != track.n_clips:
            problems.append("asset lowering count mismatch")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Intelligent Asset Retrieval demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
