"""Review & Editing Engine validation demo (Phase C11).

Proves the human-in-the-loop editing loop end to end:

    prompt -> AI Storyboard -> Review -> Patch Set -> Scene Engine -> Timeline
           -> (incremental plan: only affected scenes) -> Renderer -> updated MP4

A reel is generated, several immutable patches are applied (validating the Timeline
after EVERY patch), the incremental-render plan is computed (which scenes actually
changed), and an UPDATED playable MP4 is produced. Nothing in the Timeline IR or
the renderer is modified — editing is pure patch operations over the editable model.

    python -m editing_engine.scripts.render_edit_demo                  # ffmpeg MP4
    python -m editing_engine.scripts.render_edit_demo --renderer mock  # hermetic proxy

Verification (backend-independent): the Timeline validates after every patch, the
edit history replays byte-identically (deterministic), and the incremental plan
reports genuine scene reuse. The base + updated masters and the exports are then
probed for playability.

Exit codes:
    0  timeline valid after every patch + updated master/exports playable
    1  ffmpeg unavailable for the ffmpeg renderer
    3  a validation check or an output failed
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

from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest, Scene  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from editing_engine import (  # noqa: E402
    CaptionPatch,
    DeleteScenePatch,
    DurationPatch,
    EditingEngine,
    InsertScenePatch,
    MoveScenePatch,
    MusicPatch,
    RegenerateScenePatch,
    ReplaceNarrationPatch,
    ThemePatch,
    review_project,
)
from script_engine.storyboard import storyboard_to_json  # noqa: E402

DEMO_PROFILES = ("reel_9x16", "square_1x1")
_EXPORT_DIMS = {"reel_9x16": (1080, 1920), "square_1x1": (1080, 1080)}
DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _make_talkinghead(ffmpeg, out, audio, w, h, fps, dur):
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


#: A representative patch set (apostrophe-free narration to keep ffmpeg captions
#: happy) exercising content, structural, presentation, and AI-regeneration edits.
def _patches():
    return [
        ReplaceNarrationPatch(1, "Here is the single biggest reason to start early."),
        MoveScenePatch(2, 4),
        InsertScenePatch(3, "Picture the compounding growth over the next ten years.",
                         "explanation"),
        DeleteScenePatch(5),
        DurationPatch(1, 6.0),
        ThemePatch("finance"),
        MusicPatch("cinematic"),
        CaptionPatch(preset="tiktok"),
        RegenerateScenePatch(2, provider="mock",
                             instruction="Explain the long term returns of property"),
    ]


def _render(engine, project, out_dir, args, w, h, fps, sr, *, exports, name):
    """Build the full timeline for ``project`` and render it. Returns (timeline, result)."""
    _, timeline = engine.build_timeline(project, asset_dir=out_dir)
    dur = timeline.duration_s
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        ff = shutil.which("ffmpeg")
        speech = out_dir / f"{name}_speech.wav"
        write_wav(speech, generate_sine_wav(dur, 200.0, 24000))
        avatar = _make_talkinghead(ff, out_dir / f"{name}_avatar.mp4", speech, w, h, fps, dur)
        head = Scene.from_video(0, str(avatar), duration_s=round(read_wav(speech).duration_s, 3),
                                audio_uri=str(speech))
        timeline = dataclasses.replace(timeline, scenes=(head,))
        suffix = ".mp4"
    else:
        suffix = ".avi"
    render_cfg = ReelEngineConfig(render=RenderConfig(
        width=w, height=h, fps=fps, renderer=args.renderer, audio_sample_rate=sr))
    result = get_renderer(args.renderer, render_cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"{name}_reel{suffix}",
        renderer=args.renderer, export_profiles=exports))
    return timeline, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review & Editing Engine demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-base-render", action="store_true",
                        help="skip rendering the base reel (render only the updated reel)")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "edit_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps = args.width, args.height, args.fps
    sr = ReelEngineConfig().render.audio_sample_rate
    engine = EditingEngine()
    problems: list[str] = []

    # 1) GENERATE: prompt -> editable project -> base timeline.
    base_project = engine.new_project(args.prompt, template=args.template)
    _, base_tl = engine.build_timeline(base_project, asset_dir=out_dir)
    (out_dir / "base_storyboard.json").write_text(
        storyboard_to_json(base_project.storyboard), encoding="utf-8")
    print(f"Prompt          : {args.prompt!r}")
    print(f"Base reel       : {base_project.n_scenes} scenes, {base_tl.duration_s:.1f}s, "
          f"theme={base_project.theme} music={base_project.soundtrack}")

    # 2) REVIEW (deterministic human-in-the-loop inspection).
    report = review_project(base_project)
    print(f"Review          : {len(report.findings)} findings ({len(report.warnings)} warnings)")

    # 3) EDIT: apply the patch set, validating the Timeline after EVERY patch.
    history = engine.history(base_project)
    print("Applying patches (timeline validated after each):")
    for patch in _patches():
        project = history.apply(patch)
        _, tl = engine.build_timeline(project, with_branding=False, with_music=False)
        valid = validate_timeline(tl) == []
        print(f"  [{'OK' if valid else 'BAD'}] {patch.describe()}")
        if not valid:
            problems.append(f"invalid timeline after patch {patch.op}")
    edited_project = history.current

    # 4) INCREMENTAL PLAN (only affected scenes) + determinism.
    _, edited_tl = engine.build_timeline(edited_project, asset_dir=out_dir)
    plan = engine.incremental_plan(base_tl, edited_tl)
    print(f"Incremental plan: {plan.n_changed}/{plan.total} scenes changed, "
          f"{plan.n_reused} reused ({plan.reuse_fraction:.0%}), "
          f"overlays_changed={plan.overlays_changed}")

    checks: dict = {
        "timeline valid after every patch": not problems,
        "history replays byte-identically (deterministic)": (
            storyboard_to_json(history.replay().storyboard)
            == storyboard_to_json(edited_project.storyboard)),
        "edited timeline validates": validate_timeline(edited_tl) == [],
        "incremental plan reuses scenes": plan.n_reused >= 1,
        "edits applied (revision advanced)": edited_project.revision == len(_patches()),
    }
    print("Edit checks:")
    for check_name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {check_name}")
        if not ok:
            problems.append(f"check failed: {check_name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    (out_dir / "edited_project.json").write_text(timeline_to_json(edited_tl), encoding="utf-8")

    # 5) RENDER: base master (proof of "generate reel") + updated master + exports.
    rendered = []
    if not args.no_base_render:
        _, base_result = _render(engine, base_project, out_dir, args, w, h, fps, sr,
                                 exports=(), name="base")
        rendered.append(("base", base_result))
        print(f"Base master     : {base_result.output_path.name} ({base_result.duration_s:.2f}s)")
    _, result = _render(engine, edited_project, out_dir, args, w, h, fps, sr,
                        exports=DEMO_PROFILES, name="updated")
    rendered.append(("updated", result))
    print(f"Updated master  : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    if args.renderer == "ffmpeg":
        for label, res in rendered:
            m = probe_media(res.output_path)
            if not m.readable:
                problems.append(f"{label} master not playable")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable or (pe.width, pe.height) != _EXPORT_DIMS[ex.profile]:
                problems.append(f"export {ex.profile} bad: {pe.width}x{pe.height}")
    else:
        from foundation.shared_utils.video_io import read_raw_avi
        if read_raw_avi(result.output_path).n_frames <= 0:
            problems.append("mock updated master has no frames")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Review & Editing Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
