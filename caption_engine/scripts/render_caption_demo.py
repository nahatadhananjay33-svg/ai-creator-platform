"""Caption Engine validation demo (Phase C4).

Proves the Caption Engine's slice of the platform pipeline end to end:

    script  ->  (audio)  ->  talking-head video  ->  Timeline IR
            ->  Caption Track  ->  Renderer  ->  playable MP4
            +  SRT + WebVTT + JSON + Timeline captions

The talking-head footage is a lightweight placeholder (a labelled colour clip)
so the demo runs with no avatar/voice model weights; the *authoritative audio
duration* comes from a generated speech WAV, exactly as the real Voice Engine
would provide it. Captions are a native Timeline track — the renderer only
consumes them.

    python -m caption_engine.scripts.render_caption_demo                 # ffmpeg MP4
    python -m caption_engine.scripts.render_caption_demo --renderer mock # hermetic proxy
    python -m caption_engine.scripts.render_caption_demo --kind sentence --preset youtube

Exit codes:
    0  master + every export + subtitle file validated (playable, in sync)
    1  ffmpeg unavailable for the ffmpeg renderer
    3  an output or subtitle export failed validation
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import generate_sine_wav, read_wav, write_wav  # noqa: E402
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path  # noqa: E402

from caption_engine import CaptionEngine, load_caption_engine_config  # noqa: E402
from caption_engine.export.subtitles import write_subtitles  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import CaptionAnimation, RenderRequest, Scene  # noqa: E402
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.timeline.model import new_timeline  # noqa: E402
from reel_engine.timeline.serde import timeline_from_json, timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

DEMO_SCRIPT = (
    "Welcome to the AI Creator Platform. Captions are now a native timeline "
    "track. They stay perfectly in sync with the audio. Enjoy the show."
)
DEMO_PROFILES = ("reel_9x16", "square_1x1")


def _make_talkinghead(ffmpeg: str, out: Path, audio: Path, w: int, h: int,
                      fps: int, dur: float) -> Path:
    """A placeholder talking-head clip: a labelled colour card + the speech WAV.

    Stands in for Avatar Engine footage so the demo needs no model weights; the
    renderer treats it exactly like real avatar video."""
    vf = ("drawtext=text='TALKING HEAD':fontcolor=white:fontsize=%d:"
          "x=(w-text_w)/2:y=(h-text_h)/2" % (max(24, w // 12)))
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x2B2B3D:s={w}x{h}:r={fps}:d={dur}",
         "-i", str(audio), "-vf", vf, "-t", f"{dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)],
        check=True, capture_output=True, text=True)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Caption Engine validation demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--kind", default="karaoke",
                        choices=["sentence", "word", "karaoke", "static"])
    parser.add_argument("--preset", default="tiktok")
    parser.add_argument("--animation", default="fade", choices=["none", "fade", "pop"])
    parser.add_argument("--script", default=DEMO_SCRIPT)
    parser.add_argument("--duration", type=float, default=6.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "caption_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps = args.width, args.height, args.fps

    # 1) Audio (Voice Engine stand-in): a speech WAV whose duration bounds captions.
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(args.duration, 220.0, 24000))
    dur = read_wav(speech).duration_s
    print(f"Audio           : {speech.name} ({dur:.2f}s)")

    # 2) Talking-head scene (Avatar Engine stand-in).
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        import shutil
        avatar = _make_talkinghead(shutil.which("ffmpeg"), out_dir / "avatar.mp4",
                                   speech, w, h, fps, dur)
        scene = Scene.from_video(0, str(avatar), duration_s=round(dur, 3),
                                 audio_uri=str(speech))
        suffix = ".mp4"
    else:
        scene = Scene.simple(0, (43, 43, 61), "TALKING HEAD", duration_s=round(dur, 3))
        suffix = ".avi"

    # 3) Timeline IR + 4) Caption Track (a native track — not hardcoded).
    timeline = new_timeline([scene], title="Caption Engine demo", width=w, height=h, fps=fps)
    engine = CaptionEngine(load_caption_engine_config())
    track = engine.generate(text=args.script, duration_s=dur, kind=args.kind,
                            preset=args.preset,
                            animation=CaptionAnimation(args.animation, 0.25))
    import dataclasses
    timeline = dataclasses.replace(timeline, caption_tracks=(track,))

    project = out_dir / "project.json"
    project.write_text(timeline_to_json(timeline), encoding="utf-8")
    print(f"Captions        : kind={track.kind} preset={track.style.name} "
          f"segments={track.n_segments} words={len(track.words())} anim={args.animation}")

    # ---- synchronization validation (pre-render, explicit errors) ----
    problems = validate_timeline(timeline)
    if problems:
        print("FAIL: timeline not synchronized:\n  " + "\n  ".join(problems))
        return 3

    # 5) Render master (captions burned in) + exports.
    cfg = ReelEngineConfig(render=RenderConfig(width=w, height=h, fps=fps,
                                               renderer=args.renderer))
    result = get_renderer(args.renderer, cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"caption_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    # 6) Subtitle export: SRT + WebVTT + JSON + Timeline captions.
    subs = write_subtitles(track, out_dir, stem="captions",
                           word_level=(track.kind == "word"))

    # ---- validation ----
    problems = []

    # (a) playable master + correctly-shaped exports
    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height}")
        if abs(m.duration_s - dur) > 0.6:
            problems.append(f"master duration {m.duration_s:.2f}s != ~{dur:.2f}s")
        if not result.metadata.get("captions"):
            problems.append("captions were not burned into the master")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable:
                problems.append(f"export {ex.profile} not playable")
    else:
        from foundation.shared_utils.video_io import read_raw_avi
        vf = read_raw_avi(result.output_path)
        if vf.n_frames <= 0:
            problems.append("mock master has no frames")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    # (b) timing: captions never exceed audio; monotonic (already validated above)
    if track.duration_s > dur + 1e-6:
        problems.append(f"captions ({track.duration_s:.2f}s) exceed audio ({dur:.2f}s)")

    # (c) highlighting: word/karaoke carry per-word timings inside their segments
    if track.kind in ("word", "karaoke"):
        if not all(s.words for s in track.segments):
            problems.append("word/karaoke captions missing per-word timings")

    # (d) subtitle export: files exist, parse, and are non-empty / consistent
    srt = subs["srt"].read_text(encoding="utf-8")
    vtt = subs["vtt"].read_text(encoding="utf-8")
    first_text = track.segments[0].text.split()[0]
    if first_text not in srt:
        problems.append("SRT missing caption text")
    if not vtt.startswith("WEBVTT"):
        problems.append("WebVTT missing header")
    try:
        payload = json.loads(subs["json"].read_text(encoding="utf-8"))
        if len(payload["segments"]) != track.n_segments:
            problems.append("JSON segment count mismatch")
        # Timeline captions must round-trip losslessly through the IR serde.
        restored = timeline_from_json(timeline_to_json(timeline))
        if restored.caption_tracks[0] != track:
            problems.append("Timeline captions did not round-trip")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"subtitle JSON invalid: {exc}")

    for key, path in subs.items():
        print(f"  subtitle {key:9} {path.name}")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Caption Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
