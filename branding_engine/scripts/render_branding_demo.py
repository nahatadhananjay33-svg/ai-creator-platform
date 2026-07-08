"""Branding Engine validation demo (Phase C5).

Proves the full success-criteria pipeline end to end:

    script -> (audio) -> talking-head video -> Timeline IR
           -> Caption Track -> Branding Track -> Renderer -> playable MP4

The talking-head footage is a lightweight placeholder (a labelled colour clip)
and the audio a generated WAV, so the demo runs with no avatar/voice/model
weights. Captions and branding are both native Timeline tracks — the renderer
only consumes them.

    python -m branding_engine.scripts.render_branding_demo                  # ffmpeg MP4
    python -m branding_engine.scripts.render_branding_demo --renderer mock  # hermetic proxy
    python -m branding_engine.scripts.render_branding_demo --theme finance

Verification (backend-independent): a hermetic mock re-render of an equivalent
solid-scene timeline is pixel-checked for logo, intro, outro, lower third,
watermark, and safe-margin insets. Exit 0 when the master + exports are playable
and every branding element is verified.

Exit codes:
    0  master + exports playable and all branding elements verified
    1  ffmpeg unavailable for the ffmpeg renderer
    3  an output or a branding element failed validation
"""
from __future__ import annotations

import argparse
import dataclasses
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import generate_sine_wav, read_wav, write_wav  # noqa: E402
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path  # noqa: E402
from foundation.shared_utils.video_io import read_raw_avi  # noqa: E402

from branding_engine import BrandingEngine, load_branding_engine_config  # noqa: E402
from branding_engine.assets import default_logo_path  # noqa: E402
from caption_engine import CaptionEngine  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest, Scene, Timeline  # noqa: E402
from reel_engine.render import MockRenderer, ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.render.branding import anchor_frac, resolve_branding  # noqa: E402
from reel_engine.timeline.model import new_timeline  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

DEMO_SCRIPT = (
    "Welcome to the channel. Today we cover three quick tips. "
    "Branding is now a native timeline track. Thanks for watching."
)
DEMO_PROFILES = ("reel_9x16", "square_1x1")
_VERIFY_BG = (128, 128, 128)     # neutral scene bg for the hermetic pixel checks


def _make_talkinghead(ffmpeg, out, audio, w, h, fps, dur):
    vf = ("drawtext=text='TALKING HEAD':fontcolor=white:fontsize=%d:"
          "x=(w-text_w)/2:y=(h-text_h)/2" % (max(24, w // 12)))
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x3A3A46:s={w}x{h}:r={fps}:d={dur}",
         "-i", str(audio), "-vf", vf, "-t", f"{dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)], check=True, capture_output=True, text=True)
    return out


def _bgr(rgb):
    return bytes((rgb[2], rgb[1], rgb[0]))


def _px(frame, w, x, y):
    o = (y * w + x) * 3
    return bytes(frame[o:o + 3])


def _region_has(frame, w, h, x0, x1, y0, y1, rgb):
    b = _bgr(rgb)
    return any(_px(frame, w, x, y) == b
              for y in range(max(0, y0), min(h, y1))
              for x in range(max(0, x0), min(w, x1)))


def _verify_branding(track, dur, fps=20) -> dict:
    """Hermetic pixel verification on an equivalent solid-scene timeline."""
    scene = Scene.simple(0, _VERIFY_BG, None, duration_s=dur)
    tl = new_timeline([scene], width=200, height=356, fps=fps)
    tl = dataclasses.replace(tl, branding=track)
    cfg = ReelEngineConfig(render=RenderConfig(mock_max_dim=200, audio_sample_rate=8000))
    out = ensure_dir(Path(_verify_branding.tmp)) / "verify.avi"
    res = MockRenderer(cfg).render(RenderRequest(timeline=tl, output_path=out, renderer="mock"))
    vf = read_raw_avi(res.output_path)
    w, h, n = vf.width, vf.height, vf.n_frames
    th = track.theme
    checks: dict = {}

    # intro / outro: full-frame card colour at start / end
    if track.intro:
        checks["intro shown"] = _px(vf.frames[1], w, 1, 1) == _bgr(th.background_color)
    if track.outro:
        checks["outro shown"] = _px(vf.frames[n - 2], w, 1, 1) == _bgr(th.background_color)

    # a mid frame with no card, for the persistent overlays
    mid = vf.frames[n // 2]
    if track.logo:
        bw = int(track.logo.scale * w)
        xf, yf = anchor_frac(track.logo.position, bw / w, bw / h,
                             th.safe_margin_h, th.safe_margin_v)
        x0, y0 = int(xf * w), int(yf * h)
        checks["logo visible"] = _region_has(mid, w, h, x0, x0 + bw, y0, y0 + bw,
                                             th.primary_color)
        # safe margins: the extreme corner stays clear of the inset logo
        corner = _px(mid, w, w - 1, 0) if "right" in track.logo.position else _px(mid, w, 0, 0)
        checks["safe margins respected"] = corner == _bgr(_VERIFY_BG)
    if track.watermark:
        # blended at low opacity -> assert the resolved box changed some pixels.
        bw = int(track.watermark.scale * w)
        bh = max(2, int(0.45 * bw))
        xf, yf = anchor_frac(track.watermark.position, bw / w, bh / h,
                             th.safe_margin_h, th.safe_margin_v)
        x0, y0 = int(xf * w), int(yf * h)
        bg = _bgr(_VERIFY_BG)
        checks["watermark correct"] = any(
            _px(mid, w, x, y) != bg
            for y in range(y0, min(h, y0 + bh)) for x in range(x0, min(w, x0 + bw)))
    if track.lower_thirds:
        lt = track.lower_thirds[0]
        f_in = vf.frames[int((lt.start_s + lt.end_s) / 2 * fps)]
        band_y = int(h * (1 - th.safe_margin_v - 0.07))     # centre of the band
        in_win = _px(f_in, w, w // 2, band_y) != _bgr(_VERIFY_BG)
        # after the window the band is gone (sample a frame past it, before outro)
        t_out = min(lt.end_s + 0.5, dur - (track.outro.duration_s + 0.3 if track.outro else 0.1))
        f_out = vf.frames[max(0, int(t_out * fps))]
        out_clear = _px(f_out, w, w // 2, band_y) == _bgr(_VERIFY_BG)
        checks["lower thirds correct"] = in_win and out_clear
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Branding Engine validation demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--theme", default="corporate")
    parser.add_argument("--caption-kind", default="karaoke",
                        choices=["sentence", "word", "karaoke", "static"])
    parser.add_argument("--script", default=DEMO_SCRIPT)
    parser.add_argument("--duration", type=float, default=9.0)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "branding_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    _verify_branding.tmp = str(out_dir / "_verify")
    w, h, fps = args.width, args.height, args.fps

    # 1) Audio (Voice stand-in) -> authoritative duration.
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(args.duration, 220.0, 24000))
    dur = read_wav(speech).duration_s

    # 2) Talking-head scene (Avatar stand-in).
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        import shutil
        avatar = _make_talkinghead(shutil.which("ffmpeg"), out_dir / "avatar.mp4",
                                   speech, w, h, fps, dur)
        scene = Scene.from_video(0, str(avatar), duration_s=round(dur, 3),
                                 audio_uri=str(speech))
        suffix = ".mp4"
    else:
        scene = Scene.simple(0, (58, 58, 70), "TALKING HEAD", duration_s=round(dur, 3))
        suffix = ".avi"

    # 3) Timeline + 4) Caption Track + 5) Branding Track (all native tracks).
    timeline = new_timeline([scene], title="Branding Engine demo", width=w, height=h, fps=fps)
    captions = CaptionEngine().generate(text=args.script, duration_s=dur,
                                        kind=args.caption_kind, preset="tiktok")
    branding = BrandingEngine(load_branding_engine_config()).generate(
        reel_duration_s=dur, theme=args.theme, logo_path=default_logo_path(),
        creator="Alex Rivera", channel="Daily Insights",
        website="dailyinsights.co", handles=("@dailyinsights", "dailyinsights.co"))
    timeline = dataclasses.replace(timeline, caption_tracks=(captions,), branding=branding)

    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")
    print(f"Theme           : {branding.theme.name}")
    print(f"Branding        : intro={branding.intro is not None} logo={branding.logo is not None} "
          f"lower_third={len(branding.lower_thirds)} watermark={branding.watermark is not None} "
          f"outro={branding.outro is not None}")

    problems = validate_timeline(timeline)
    if problems:
        print("FAIL: timeline invalid:\n  " + "\n  ".join(problems))
        return 3

    # 6) Render master (captions + branding composited) + exports.
    cfg = ReelEngineConfig(render=RenderConfig(width=w, height=h, fps=fps, renderer=args.renderer))
    result = get_renderer(args.renderer, cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"branded_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    # ---- validation ----
    problems = []
    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height}")
        if not result.metadata.get("branding"):
            problems.append("branding was not composited into the master")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable:
                problems.append(f"export {ex.profile} not playable")
    else:
        vf = read_raw_avi(result.output_path)
        if vf.n_frames <= 0:
            problems.append("mock master has no frames")

    # Backend-independent branding verification (hermetic mock pixel checks).
    checks = _verify_branding(branding, dur)
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"branding check failed: {name}")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Branding Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
