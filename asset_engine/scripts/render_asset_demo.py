"""Visual Asset Engine validation demo (Phase C6).

Proves the full success-criteria pipeline end to end:

    script -> (audio) -> talking-head video -> Timeline IR -> Caption Track
           -> Branding Track -> Visual Asset Track -> Renderer -> playable MP4

The talking-head footage and B-roll are lightweight local placeholders (labelled
colour clips / PNGs) and the audio a generated WAV, so the demo runs with no
avatar/voice/model weights and no downloads. Visual assets are a native Timeline
track — the renderer only consumes them.

    python -m asset_engine.scripts.render_asset_demo                  # ffmpeg MP4
    python -m asset_engine.scripts.render_asset_demo --renderer mock  # hermetic proxy

Verification (backend-independent): a hermetic mock re-render of an equivalent
solid-scene timeline is pixel-checked for asset timing, layering, positioning
(PIP corner + split half), no clipping, and no missing assets. Exit 0 when the
master + exports are playable and every asset check passes.

Exit codes:
    0  master + exports playable and all asset checks pass
    1  ffmpeg unavailable for the ffmpeg renderer
    3  an output or an asset check failed
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
from caption_engine import CaptionEngine  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import RenderRequest, Scene, Timeline  # noqa: E402
from reel_engine.render import MockRenderer, ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.render.assets import asset_mock_color  # noqa: E402
from reel_engine.timeline.model import new_timeline  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

DEMO_SCRIPT = (
    "Here is the intro. Now look at this chart. Back to me for a moment. "
    "And here is some footage. Thanks for watching."
)
DEMO_PROFILES = ("reel_9x16", "square_1x1")
_VERIFY_BG = (128, 128, 128)     # neutral scene bg for the hermetic pixel checks
REEL_DUR = 14.0


def _make_talkinghead(ffmpeg, out, audio, w, h, fps, dur):
    vf = ("drawtext=text='TALKING HEAD':fontcolor=white:fontsize=%d:"
          "x=(w-text_w)/2:y=(h-text_h)/2" % (max(24, w // 12)))
    import subprocess
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"color=c=0x33384A:s={w}x{h}:r={fps}:d={dur}",
         "-i", str(audio), "-vf", vf, "-t", f"{dur}",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)], check=True, capture_output=True, text=True)
    return out


#: The demo's B-roll plan (clip_id, kind, layout, params, window, animation, z).
def _asset_specs(img: str, vid: str) -> list[AssetSpec]:
    return [
        # image B-roll (full screen) — "look at this chart"
        AssetSpec(img, 2.0, 5.0, kind="chart", layout="full_screen",
                  animation_in="fade_in", animation_out="fade_out",
                  z_index=0, clip_id="image_broll"),
        # picture-in-picture (overlaps the image B-roll -> exercises layering)
        AssetSpec(img, 3.0, 4.5, kind="chart", layout="picture_in_picture",
                  layout_params={"corner": "top_right", "scale": 0.30, "margin": 0.06},
                  animation_in="none", animation_out="none",
                  z_index=2, clip_id="pip"),
        # split-screen video — talking head on the left, footage on the right
        AssetSpec(vid, 6.0, 8.5, kind="video", layout="split_screen",
                  layout_params={"side": "right"}, animation_in="slide_left",
                  animation_out="none", z_index=1, clip_id="split"),
        # video B-roll (full screen) — "here is some footage"
        AssetSpec(vid, 10.0, 13.0, kind="video", layout="full_screen",
                  animation_in="cross_dissolve", animation_out="fade_out",
                  z_index=0, clip_id="video_broll"),
    ]


def _bgr(rgb):
    return bytes((rgb[2], rgb[1], rgb[0]))


def _px(frame, w, x, y):
    o = (y * w + x) * 3
    return bytes(frame[o:o + 3])


def _has(frame, w, h, rgb):
    b = _bgr(rgb)
    return any(frame[i * 3:i * 3 + 3] == b for i in range(w * h))


def _verify_assets(track, dur, fps=20) -> dict:
    """Hermetic pixel verification on an equivalent solid-scene timeline."""
    scene = Scene.simple(0, _VERIFY_BG, None, duration_s=dur)
    tl = new_timeline([scene], width=200, height=356, fps=fps)
    tl = dataclasses.replace(tl, asset_tracks=(track,))
    cfg = ReelEngineConfig(render=RenderConfig(mock_max_dim=200, audio_sample_rate=8000))
    out = ensure_dir(Path(_verify_assets.tmp)) / "verify.avi"
    res = MockRenderer(cfg).render(RenderRequest(timeline=tl, output_path=out, renderer="mock"))
    vf = read_raw_avi(res.output_path)
    w, h = vf.width, vf.height
    col = {c.clip_id: asset_mock_color(c.clip_id) for c in track.clips}

    def frame(t):
        return vf.frames[min(vf.n_frames - 1, int(t * fps))]

    checks: dict = {}
    checks["image B-roll timing"] = (
        _has(frame(4.0), w, h, col["image_broll"])          # in window [2,5]
        and not _has(frame(9.0), w, h, col["image_broll"]))  # gone in the gap
    checks["video B-roll timing"] = (
        _has(frame(11.5), w, h, col["video_broll"])          # in window [10,13]
        and not _has(frame(9.0), w, h, col["video_broll"]))
    # PIP positioning + no clipping: the PIP shows in the top-right but is inset,
    # so the extreme corner is NOT the PIP (it never reaches the frame edge).
    fp = frame(3.7)
    checks["picture-in-picture position"] = (
        _px(fp, w, int(w * 0.82), int(h * 0.12)) == _bgr(col["pip"])
        and _px(fp, w, w - 1, 0) != _bgr(col["pip"]))
    # correct layering: PIP (z=2) paints on top of the full-screen image B-roll (z=0)
    checks["correct layering"] = _px(fp, w, int(w * 0.82), int(h * 0.12)) == _bgr(col["pip"])
    # split-screen: footage fills the right half, talking-head (bg) the left
    fs = frame(7.0)
    checks["split-screen position"] = (
        _px(fs, w, int(w * 0.75), h // 2) == _bgr(col["split"])
        and _px(fs, w, int(w * 0.25), h // 2) == _bgr(_VERIFY_BG))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visual Asset Engine validation demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-overlays", action="store_true",
                        help="skip captions + branding (assets only)")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "asset_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    _verify_assets.tmp = str(out_dir / "_verify")
    w, h, fps, dur = args.width, args.height, args.fps, REEL_DUR

    # 1) Audio (Voice stand-in) -> duration bound.
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(dur, 220.0, 24000))
    dur = read_wav(speech).duration_s

    # 2) Local B-roll assets (deterministic placeholders — no downloads/AI).
    img = generate_image(out_dir / "chart.png", width=1280, height=720,
                         color=(30, 90, 150), label="chart")
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        ff = shutil.which("ffmpeg")
        vid = generate_video(ff, out_dir / "broll.mp4", width=1280, height=720,
                             fps=fps, duration_s=5.0)
        scene = Scene.from_video(0, str(_make_talkinghead(
            ff, out_dir / "avatar.mp4", speech, w, h, fps, dur)),
            duration_s=round(dur, 3), audio_uri=str(speech))
        suffix = ".mp4"
    else:
        vid = generate_image(out_dir / "broll.png", label="video")  # stand-in for mock
        scene = Scene.simple(0, (51, 56, 74), "TALKING HEAD", duration_s=round(dur, 3))
        suffix = ".avi"

    # 3) Timeline + 4) Visual Asset Track (a native track — not hardcoded).
    timeline = new_timeline([scene], title="Visual Asset Engine demo",
                            width=w, height=h, fps=fps)
    track = AssetEngine().build(_asset_specs(str(img), str(vid)))
    timeline = dataclasses.replace(timeline, asset_tracks=(track,))

    # (optional) also stack captions + branding to show the complete pipeline.
    if not args.no_overlays:
        captions = CaptionEngine().generate(text=DEMO_SCRIPT, duration_s=dur,
                                            kind="karaoke", preset="tiktok")
        branding = BrandingEngine().generate(reel_duration_s=dur, theme="modern",
                                             logo_path=default_logo_path(),
                                             creator="Alex Rivera", channel="Daily Insights")
        timeline = dataclasses.replace(timeline, caption_tracks=(captions,), branding=branding)

    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")
    print(f"Assets          : {track.n_clips} clips "
          f"[{', '.join(c.layout.kind for c in track.clips)}]")

    problems = validate_timeline(timeline)
    if problems:
        print("FAIL: timeline invalid:\n  " + "\n  ".join(problems))
        return 3

    # 5) Render master (assets + captions + branding composited) + exports.
    cfg = ReelEngineConfig(render=RenderConfig(width=w, height=h, fps=fps, renderer=args.renderer))
    result = get_renderer(args.renderer, cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"asset_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    # ---- validation ----
    problems = []
    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height}")
        if not result.metadata.get("assets"):
            problems.append("assets were not composited into the master")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable:
                problems.append(f"export {ex.profile} not playable")
            prof_ok = (pe.width, pe.height) == (
                {"reel_9x16": (1080, 1920), "square_1x1": (1080, 1080)}[ex.profile])
            if not prof_ok:
                problems.append(f"export {ex.profile} wrong aspect: {pe.width}x{pe.height}")
    else:
        vf = read_raw_avi(result.output_path)
        if vf.n_frames <= 0:
            problems.append("mock master has no frames")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    # Backend-independent asset verification (hermetic mock pixel checks).
    for name, ok in _verify_assets(track, dur).items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"asset check failed: {name}")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Visual Asset Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
