"""Scene & Storyboard Planning Engine validation demo (Phase C7).

Proves the full success-criteria pipeline end to end, driven from a plain script:

    script -> Storyboard -> Timeline Plan -> (Voice) -> Avatar -> Timeline
           -> Caption Track -> Branding Track -> Visual Asset Track
           -> Renderer -> playable MP4

The Scene Engine is the new front of the pipeline: it *plans* a finished script
into a deterministic :class:`Storyboard` (typed, timed scenes with narration and
visual slots) and lowers it into the existing Timeline IR. Everything downstream
is reused, not reinvented — captions come from the storyboard's own timing, the
avatar/B-roll are lightweight local stand-ins (labelled colour cards / PNGs) and
the audio a generated WAV, so the demo runs with no models, weights, or downloads.

Crucially, the planner only *requests* visual assets (:class:`AssetSlot`); here we
make the hand-off concrete by satisfying each requested slot with a deterministic
placeholder via the Visual Asset Engine — exactly what a real Asset Engine will
do later — so the rendered reel exercises the complete chain.

    python -m scene_engine.scripts.render_scene_demo                  # ffmpeg MP4
    python -m scene_engine.scripts.render_scene_demo --renderer mock  # hermetic proxy
    python -m scene_engine.scripts.render_scene_demo --no-assets      # captions only

Verification (backend-independent, no ffmpeg needed for the plan checks): the
storyboard and lowered timeline are asserted for correct scene count, correct
per-scene timing (floors honoured, total duration), correct ordering, NO overlaps,
NO gaps, aligned captions, the planned asset-slot count, and a clean pass of the
Timeline validator. Exit 0 when those hold and the master + exports are playable.

Exit codes:
    0  storyboard + timeline valid, master + exports playable, all checks pass
    1  ffmpeg unavailable for the ffmpeg renderer
    3  an output or a determinism/plan check failed
"""
from __future__ import annotations

import argparse
import dataclasses
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import generate_sine_wav, read_wav, write_wav  # noqa: E402
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path  # noqa: E402
from foundation.shared_utils.video_io import read_raw_avi  # noqa: E402

from asset_engine import AssetEngine, AssetSpec  # noqa: E402
from asset_engine.providers.placeholder import generate_image, generate_video  # noqa: E402
from branding_engine import BrandingEngine  # noqa: E402
from branding_engine.assets import default_logo_path  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest, Scene  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from scene_engine import SceneEngine  # noqa: E402
from scene_engine.storyboard.serde import storyboard_to_json  # noqa: E402

#: A ~40-second finished script that exercises many scene-type rule paths:
#: hook, explanation, chart/data, comparison, bullet list, video insert, image
#: insert, and a closing call-to-action. Blank lines are paragraph breaks.
DEMO_SCRIPT = (
    "Ever wondered why some short videos explode while others flop?\n\n"
    "It almost always comes down to the first three seconds. "
    "The data shows that 65% of viewers scroll away before the payoff.\n\n"
    "Look at this chart of viewer retention over the first ten seconds.\n\n"
    "Compared to long videos, a reel has to earn attention immediately, "
    "whereas a documentary can take its time.\n\n"
    "Here are three fixes. First, open with a bold question. "
    "Second, cut the slow intro. Third, show the result up front.\n\n"
    "Watch how this creator nails the opening in a single clip.\n\n"
    "So if that was useful, subscribe and follow for a new tip every week.\n\n"
)
DEMO_PROFILES = ("reel_9x16", "square_1x1")
_EXPORT_DIMS = {"reel_9x16": (1080, 1920), "square_1x1": (1080, 1080)}


def _make_talkinghead(ffmpeg, out, audio, w, h, fps, dur):
    """A labelled colour clip muxed with the WAV — the Avatar/Voice stand-in."""
    import subprocess
    vf = ("drawtext=text='TALKING HEAD':fontcolor=white:fontsize=%d:"
          "x=(w-text_w)/2:y=(h-text_h)/2" % (max(24, w // 12)))
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x24283A:s={w}x{h}:r={fps}:d={dur}",
         "-i", str(audio), "-vf", vf, "-t", f"{dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)], check=True, capture_output=True, text=True)
    return out


def _assets_from_slots(storyboard, img: str, vid: str) -> list[AssetSpec]:
    """Satisfy each planned :class:`AssetSlot` with a deterministic placeholder.

    This is the Scene Engine -> Visual Asset Engine hand-off made concrete: the
    planner requested these slots (kind, layout, window); here we resolve every
    one to a local placeholder file so the reel renders the real B-roll track. A
    later Asset Engine swaps the placeholders for retrieved/generated media — the
    slots (and their timing) are unchanged.
    """
    specs: list[AssetSpec] = []
    for slot in storyboard.all_asset_slots:
        src = vid if slot.kind == "video" else img
        specs.append(AssetSpec(
            src, round(slot.start_s, 3), round(slot.end_s, 3),
            kind=slot.kind, layout=slot.layout,
            animation_in="fade_in", animation_out="fade_out",
            z_index=slot.z_index, clip_id=slot.slot_id))
    return specs


def _verify_plan(storyboard, timeline, cfg, *, expect_assets: bool) -> dict:
    """Backend-independent determinism/plan checks on the storyboard + timeline.

    Every check is pure data (no renderer, no ffmpeg): the deterministic proof
    that scene splitting, classification, timing, ordering, and lowering are all
    correct. Returns an ordered ``name -> ok`` map.
    """
    scenes = storyboard.scenes
    n = storyboard.n_scenes
    checks: dict = {}

    # correct scene count: non-empty, and the timeline mirrors the storyboard.
    checks["scene count > 0"] = n > 0
    checks["timeline mirrors storyboard scene count"] = timeline.n_scenes == n

    # correct ordering: indices 0..n-1 in order, scene ids sequential.
    checks["scene indices sequential"] = [s.index for s in scenes] == list(range(n))
    checks["scene ids match order"] = all(
        s.scene_id == f"scene-{i:03d}" for i, s in enumerate(scenes))

    # correct timing: every window honours its floor; nothing is zero-length.
    checks["every scene has positive duration"] = all(s.duration_s > 0 for s in scenes)
    checks["windows honour min floor"] = all(
        s.duration_s >= cfg.min_scene_duration_s - 1e-6 for s in scenes)
    checks["cta/outro honour preferred floor"] = all(
        s.duration_s >= cfg.preferred_cta_duration_s - 1e-6
        for s in scenes if s.scene_type.value == "call_to_action")

    # NO overlaps and NO gaps: contiguous absolute windows (transition_s == 0).
    gap = cfg.transition_s
    contiguous = all(
        abs(scenes[i].start_s - (scenes[i - 1].end_s + gap)) <= 1e-6
        for i in range(1, n))
    checks["no gaps / no overlaps (contiguous)"] = contiguous
    checks["starts monotonic increasing"] = all(
        scenes[i].start_s >= scenes[i - 1].end_s - 1e-6 for i in range(1, n))
    checks["duration = sum of scenes"] = abs(
        storyboard.duration_s - sum(s.duration_s for s in scenes)) <= 1e-6

    # captions aligned: one segment per narrated scene, exact windows.
    track = timeline.caption_tracks[0] if timeline.caption_tracks else None
    narrated = [s for s in scenes if s.narration.text.strip()]
    checks["one caption per narrated scene"] = bool(track) and (
        len(track.segments) == len(narrated))
    if track:
        checks["caption windows match scene windows"] = all(
            abs(seg.start_s - sc.timing.start_s) <= 1e-6
            and abs(seg.end_s - sc.timing.end_s) <= 1e-6
            for seg, sc in zip(track.segments, narrated))

    # asset slots planned (the Asset Engine hand-off): present when expected.
    slot_kinds = {a.kind for a in storyboard.all_asset_slots}
    checks["asset slots planned"] = (bool(storyboard.all_asset_slots) == expect_assets)
    checks["asset kinds valid"] = slot_kinds.issubset({
        "image", "video", "chart", "map", "screenshot", "document",
        "icon", "illustration", "logo"})

    # the Timeline validator — the same invariants the renderer relies on.
    checks["timeline validator passes"] = validate_timeline(timeline) == []
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scene Planning Engine validation demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--script", default=DEMO_SCRIPT)
    parser.add_argument("--no-assets", action="store_true",
                        help="skip satisfying asset slots (captions only)")
    parser.add_argument("--no-branding", action="store_true", help="skip the branding track")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "scene_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps = args.width, args.height, args.fps

    # 1) PLAN: script -> Storyboard (deterministic, no AI, no I/O).
    engine = SceneEngine()
    cfg = engine.config
    storyboard = engine.plan(args.script, title="Scene Engine demo",
                             creator="Alex Rivera", channel="Daily Insights")
    (out_dir / "storyboard.json").write_text(
        storyboard_to_json(storyboard), encoding="utf-8")

    print(f"Storyboard      : {storyboard.n_scenes} scenes, "
          f"{storyboard.duration_s:.2f}s, {storyboard.word_count} words, "
          f"{len(storyboard.all_asset_slots)} asset slots")
    for s in storyboard.scenes:
        assets = ",".join(a.kind for a in s.visual.assets) or "-"
        print(f"  [{s.index}] {s.scene_type.label:15} "
              f"{s.start_s:6.2f}-{s.end_s:6.2f}s  ({s.duration_s:4.2f}s)  "
              f"words={s.narration.word_count:2d}  assets={assets}")

    # 2) LOWER: Storyboard -> Timeline IR (scenes as solid cards + captions).
    #    Captions come straight from the plan's own timing, so they can't drift.
    timeline = engine.build_timeline(storyboard, width=w, height=h, fps=fps)

    # ---- backend-independent determinism / plan validation ----
    #    Run BEFORE any render-time substitution (below the avatar stand-in
    #    collapses the per-scene cards into one clip): these checks are about the
    #    plan and its lowering, which are backend-independent and deterministic.
    problems: list[str] = []
    checks = _verify_plan(storyboard, timeline, cfg,
                          expect_assets=not args.no_assets)
    # determinism: replanning the identical script is byte-for-byte identical.
    replan = SceneEngine(cfg).plan(args.script, title="Scene Engine demo",
                                   creator="Alex Rivera", channel="Daily Insights")
    checks["replan is byte-identical (deterministic)"] = (
        storyboard_to_json(replan) == storyboard_to_json(storyboard))
    print("Plan checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"plan check failed: {name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    # 3) VOICE stand-in: a WAV spanning the planned reel -> authoritative duration.
    dur = storyboard.duration_s
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(dur, 220.0, 24000))
    dur = read_wav(speech).duration_s

    # 4) AVATAR stand-in: render scenes as labelled solid cards (ffmpeg) or keep
    #    the lowered solid-card timeline as-is (mock). Either way the renderer is
    #    untouched; the Scene Engine only feeds it.
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        ff = shutil.which("ffmpeg")
        avatar = _make_talkinghead(ff, out_dir / "avatar.mp4", speech, w, h, fps, dur)
        head = Scene.from_video(0, str(avatar), duration_s=round(dur, 3),
                                audio_uri=str(speech))
        timeline = dataclasses.replace(timeline, scenes=(head,))
        suffix = ".mp4"
    else:
        suffix = ".avi"

    # 5) VISUAL ASSETS: satisfy each planned slot with a placeholder -> AssetTrack.
    if not args.no_assets and storyboard.all_asset_slots:
        img = generate_image(out_dir / "broll.png", width=1280, height=720,
                             color=(30, 90, 150), label="B-ROLL")
        if args.renderer == "ffmpeg":
            vid = generate_video(shutil.which("ffmpeg"), out_dir / "broll.mp4",
                                 width=1280, height=720, fps=fps, duration_s=6.0)
        else:
            vid = generate_image(out_dir / "broll_v.png", label="VIDEO")
        track = AssetEngine().build(_assets_from_slots(storyboard, str(img), str(vid)))
        timeline = dataclasses.replace(timeline, asset_tracks=(track,))
        print(f"Visual assets   : {track.n_clips} clips resolved from planned slots "
              f"[{', '.join(c.layout.kind for c in track.clips)}]")

    # 6) BRANDING: a native branding track (intro/logo/lower-third/outro).
    if not args.no_branding:
        branding = BrandingEngine().generate(
            reel_duration_s=dur, theme="modern", logo_path=default_logo_path(),
            creator="Alex Rivera", channel="Daily Insights")
        timeline = dataclasses.replace(timeline, branding=branding)

    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")

    # 7) RENDER: master (scenes + captions + assets + branding) + exports.
    render_cfg = ReelEngineConfig(render=RenderConfig(
        width=w, height=h, fps=fps, renderer=args.renderer))
    result = get_renderer(args.renderer, render_cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"scene_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height}")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable:
                problems.append(f"export {ex.profile} not playable")
            if (pe.width, pe.height) != _EXPORT_DIMS[ex.profile]:
                problems.append(f"export {ex.profile} wrong aspect: {pe.width}x{pe.height}")
    else:
        vf = read_raw_avi(result.output_path)
        if vf.n_frames <= 0:
            problems.append("mock master has no frames")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Scene Planning Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
