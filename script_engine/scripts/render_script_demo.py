"""AI Prompt & Storyboard Engine validation demo (Phase C10).

Proves the stop-condition pipeline end to end, driven entirely from a PROMPT:

    prompt -> AI Storyboard (provider) -> Scene Engine -> Timeline IR
           -> Caption -> Branding -> Visual Assets -> Music -> Renderer -> MP4

The AI layer (default: the deterministic MockProvider — no API key) only produces
the structured storyboard; every stage after it is the EXISTING deterministic
pipeline, reused unchanged. The AI never generates video, never touches the
Timeline IR, and never talks to the renderer.

    python -m script_engine.scripts.render_script_demo                  # ffmpeg MP4
    python -m script_engine.scripts.render_script_demo --renderer mock  # hermetic proxy
    python -m script_engine.scripts.render_script_demo --provider anthropic  # live LLM (needs key)
    python -m script_engine.scripts.render_script_demo --prompt "How compound interest works" --template finance

Verification (backend-independent): the AI storyboard is valid, the deterministic
scene plan is valid (correct scene count, no gaps/overlaps), the timeline passes
the Timeline validator, and — with the default MockProvider — the whole thing is
byte-identical on a re-run. The master + exports are then probed for playability.
Exit 0 when a storyboard successfully produces a playable reel.

Exit codes:
    0  storyboard/scene-plan/timeline valid + master/exports playable
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

from asset_engine import AssetEngine  # noqa: E402
from asset_engine.providers.placeholder import generate_image  # noqa: E402
from branding_engine import BrandingEngine  # noqa: E402
from branding_engine.assets import default_logo_path  # noqa: E402
from music_engine import MusicEngine  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest, Scene  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from script_engine import ScriptEngine, storyboard_to_json, validate_storyboard  # noqa: E402
from script_engine.config.settings import ScriptEngineConfig  # noqa: E402

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


def _build_catalog(slots, root: Path) -> Path:
    """A small deterministic local library covering the planned asset slots."""
    from asset_engine.catalog.index import tokenize_tags
    for slot in slots:
        tags = tokenize_tags(slot.hint)[:3]
        stem = "_".join(tags) if tags else "topic"
        generate_image(root / f"{slot.kind}s" / f"ideal_{stem}.png", width=1080, height=1920)
    return root


def _verify_plan(ai_sb, scene_sb, timeline, cfg) -> dict:
    """Backend-independent checks: storyboard, scene plan, and timeline validity."""
    checks: dict = {}
    checks["AI storyboard valid"] = validate_storyboard(
        ai_sb, min_scenes=cfg.min_scenes, max_scenes=cfg.max_scenes) == []
    checks["storyboard has scenes"] = ai_sb.n_scenes > 0
    checks["scene plan has scenes"] = scene_sb.n_scenes > 0
    # correct timing: contiguous windows (no gaps, no overlaps)
    contiguous = all(
        abs(scene_sb.scenes[i].start_s - scene_sb.scenes[i - 1].end_s) <= 1e-6
        for i in range(1, scene_sb.n_scenes))
    checks["scene plan has no gaps/overlaps"] = contiguous
    checks["timeline mirrors scene plan"] = timeline.n_scenes == scene_sb.n_scenes
    checks["timeline validates"] = validate_timeline(timeline) == []
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Prompt & Storyboard Engine demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-overlays", action="store_true",
                        help="skip branding + assets + music (captions only)")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "script_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps = args.width, args.height, args.fps
    sr = ReelEngineConfig().render.audio_sample_rate

    # 1) PROMPT -> AI Storyboard -> deterministic Scene-Planner Storyboard.
    cfg = ScriptEngineConfig(provider=args.provider, template=args.template)
    engine = ScriptEngine(cfg)
    ai_sb, scene_sb = engine.plan(args.prompt, template=args.template, provider=args.provider)
    (out_dir / "ai_storyboard.json").write_text(storyboard_to_json(ai_sb), encoding="utf-8")
    print(f"Prompt          : {args.prompt!r}")
    print(f"AI Storyboard   : provider={ai_sb.provider} model={ai_sb.model} "
          f"template={ai_sb.template}  {ai_sb.n_scenes} scenes, {ai_sb.word_count} words")
    for s in ai_sb.scenes:
        print(f"  [{s.scene_type:14}] {s.narration}")
    print(f"Scene plan      : {scene_sb.n_scenes} scenes, {scene_sb.duration_s:.1f}s "
          f"[{', '.join(t.value for t in scene_sb.scene_types())}]")

    # 2) LOWER: scene plan -> Timeline IR (scenes + captions), via the Scene Engine.
    timeline = engine.scene_engine.build_timeline(scene_sb, width=w, height=h, fps=fps)
    dur = scene_sb.duration_s

    # ---- backend-independent validation (BEFORE any render substitution) ----
    problems: list[str] = []
    checks = _verify_plan(ai_sb, scene_sb, timeline, cfg)
    if args.provider == "mock":
        ai2, sc2 = ScriptEngine(cfg).plan(args.prompt, template=args.template, provider="mock")
        checks["deterministic (mock replan byte-identical)"] = (
            storyboard_to_json(ai2) == storyboard_to_json(ai_sb))
    print("Pipeline checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"check failed: {name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    # 3) VOICE stand-in + 4) AVATAR (ffmpeg renders scenes as a talking-head clip).
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(dur, 200.0, 24000))
    dur = round(read_wav(speech).duration_s, 3)
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        ff = shutil.which("ffmpeg")
        avatar = _make_talkinghead(ff, out_dir / "avatar.mp4", speech, w, h, fps, dur)
        head = Scene.from_video(0, str(avatar), duration_s=dur, audio_uri=str(speech))
        timeline = dataclasses.replace(timeline, scenes=(head,))
        suffix = ".mp4"
    else:
        suffix = ".avi"

    # 5) BRANDING + 6) VISUAL ASSETS + 7) MUSIC — the full downstream pipeline.
    if not args.no_overlays:
        branding = BrandingEngine().generate(
            reel_duration_s=dur, theme="modern", logo_path=default_logo_path(),
            creator="Alex Rivera", channel="Daily Insights")
        timeline = dataclasses.replace(timeline, branding=branding)
        slots = list(scene_sb.all_asset_slots)
        if slots:
            library = _build_catalog(slots, out_dir / "library")
            track, _res = AssetEngine().resolve_slots(
                slots, frame_width=w, frame_height=h, library_dir=library, strict=False)
            if track.n_clips:
                timeline = dataclasses.replace(timeline, asset_tracks=(track,))
                print(f"Visual assets   : {track.n_clips} slots resolved from catalog")
        music = MusicEngine().generate_for_timeline(
            timeline, soundtrack="ambient", sample_rate=sr, asset_dir=out_dir)
        timeline = dataclasses.replace(timeline, music_tracks=(music,))

    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")
    if validate_timeline(timeline):
        print("FAIL: assembled timeline invalid:\n  "
              + "\n  ".join(validate_timeline(timeline)))
        return 3

    # 8) RENDER: master + exports.
    render_cfg = ReelEngineConfig(render=RenderConfig(
        width=w, height=h, fps=fps, renderer=args.renderer, audio_sample_rate=sr))
    result = get_renderer(args.renderer, render_cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"script_reel{suffix}",
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
            if not pe.readable or (pe.width, pe.height) != _EXPORT_DIMS[ex.profile]:
                problems.append(f"export {ex.profile} bad: {pe.width}x{pe.height}")
    else:
        from foundation.shared_utils.video_io import read_raw_avi
        if read_raw_avi(result.output_path).n_frames <= 0:
            problems.append("mock master has no frames")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== AI Prompt & Storyboard Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
