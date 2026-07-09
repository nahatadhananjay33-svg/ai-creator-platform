"""Music & Audio Mixing Engine validation demo (Phase C8).

Proves the full success-criteria pipeline end to end:

    script -> (voice) -> talking head -> Timeline IR -> Caption Track
           -> Branding Track -> Visual Asset Track -> MUSIC TRACK
           -> Renderer -> playable MP4

Every visual is a lightweight local placeholder (labelled colour cards / PNGs)
and the audio is generated (a voice WAV + a deterministic procedural soundtrack),
so the demo runs with no models, weights, or downloads. Music is a native
Timeline track — the renderer *mixes* it under the voice; it is never hardcoded.

    python -m music_engine.scripts.render_music_demo                  # ffmpeg MP4
    python -m music_engine.scripts.render_music_demo --renderer mock  # hermetic proxy
    python -m music_engine.scripts.render_music_demo --soundtrack upbeat

Verification (backend-independent): the deterministic voice+music mix the renderer
muxes is checked directly from samples for background music, speech ducking (music
dips under the caption windows), fade in/out, looping (a short bed tiled to fill
the reel), correct timing, no clipping, and byte-identical determinism. The
master + exports are then probed for playability. Exit 0 when all hold.

Exit codes:
    0  mix verified + master/exports playable
    1  ffmpeg unavailable for the ffmpeg renderer
    3  a mix check or an output failed
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
from foundation.shared_utils.audio_mix import to_float  # noqa: E402
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path  # noqa: E402

from asset_engine import AssetEngine, AssetSpec  # noqa: E402
from asset_engine.providers.placeholder import generate_image, generate_video  # noqa: E402
from branding_engine import BrandingEngine  # noqa: E402
from branding_engine.assets import default_logo_path  # noqa: E402
from reel_engine.config import ReelEngineConfig, RenderConfig  # noqa: E402
from reel_engine.interfaces.types import (  # noqa: E402
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    RenderRequest,
    Scene,
)
from reel_engine.render import ffprobe_available, get_renderer, probe_media  # noqa: E402
from reel_engine.render.music import mix_timeline_audio, speech_windows  # noqa: E402
from reel_engine.timeline.model import new_timeline  # noqa: E402
from reel_engine.timeline.serde import timeline_to_json  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from music_engine import MusicEngine  # noqa: E402

REEL_DUR = 20.0
DEMO_PROFILES = ("reel_9x16", "square_1x1")
_EXPORT_DIMS = {"reel_9x16": (1080, 1920), "square_1x1": (1080, 1080)}
#: Narration windows (absolute reel time). The GAPS — [0,3], [7,10], [16,20] —
#: are deliberately music-only so ducking, fade-in and fade-out are all legible.
CAPTIONS = ((3.0, 7.0, "First, the hook grabs attention."),
            (10.0, 16.0, "Then the payoff lands with music under the voice."))


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


def _caption_track() -> CaptionTrack:
    segs = tuple(CaptionSegment(segment_id=f"seg-{i:03d}", index=i, text=t,
                                start_s=s, end_s=e)
                 for i, (s, e, t) in enumerate(CAPTIONS))
    return CaptionTrack(track_id="captions", kind="sentence", segments=segs,
                        style=CaptionStyle(name="clean"))


def _rms(f, sr, a, b):
    seg = f[int(a * sr):int(b * sr)]
    return (sum(x * x for x in seg) / max(1, len(seg))) ** 0.5


def _verify_mix(timeline, sr) -> tuple:
    """Backend-independent checks on the music DSP.

    Mixes over a SILENT voice bed so the checks isolate the music contribution
    (fades / ducking / looping are properties of the music track and the mixer,
    identical in both backends). The full voice+music playability is proven
    separately by probing the rendered master."""
    n_total = round(timeline.duration_s * sr)
    wav = mix_timeline_audio(timeline, sr, voice=[0.0] * n_total)
    f = to_float(wav.samples)
    n = len(f)
    windows = speech_windows(timeline)
    # no-clip is checked on the FULL voice+music mix (what actually gets muxed).
    pk = max((abs(x) for x in to_float(mix_timeline_audio(timeline, sr).samples)),
             default=0.0)
    gap = _rms(f, sr, 7.5, 9.5)              # a music-only gap between captions
    # full-music windows (no speech, no fade): one in the first bed play (<8s),
    # one in a later iteration (>8s) — comparable energy proves the bed loops.
    loop_early = _rms(f, sr, 2.0, 2.9)
    loop_late = _rms(f, sr, 8.3, 9.7)

    checks = {
        "correct timing (mix length == reel)":
            abs(n - round(timeline.duration_s * sr)) <= 1,
        "background music present": gap > 0.02,
        "fade-in ramps up from start": _rms(f, sr, 0.0, 0.4) < 0.6 * gap,
        "fade-out ramps down to end": _rms(f, sr, REEL_DUR - 0.4, REEL_DUR) < 0.6 * gap,
        "speech ducking dips music under narration":
            _rms(f, sr, 4.0, 6.5) < 0.7 * gap,
        "looping fills past the source bed":
            loop_early > 0.03 and loop_late > 0.5 * loop_early,
        "no clipping (peak < 1.0)": pk < 1.0,
        "speech windows derived from captions": windows == [(3.0, 7.0), (10.0, 16.0)],
    }
    return checks, pk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Music & Audio Mixing Engine demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--soundtrack", default="ambient",
                        choices=["ambient", "upbeat", "lofi", "cinematic"])
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--no-overlays", action="store_true",
                        help="skip branding + assets (music + captions only)")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "music_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    w, h, fps, dur = args.width, args.height, args.fps, REEL_DUR
    sr = ReelEngineConfig().render.audio_sample_rate

    # 1) Voice stand-in: a WAV spanning the reel -> authoritative duration.
    speech = out_dir / "speech.wav"
    write_wav(speech, generate_sine_wav(dur, 200.0, 24000))
    dur = round(read_wav(speech).duration_s, 3)

    # 2) Talking-head scene (Avatar stand-in) + 3) Timeline.
    if args.renderer == "ffmpeg":
        ensure_ffmpeg_on_path()
        ff = shutil.which("ffmpeg")
        avatar = _make_talkinghead(ff, out_dir / "avatar.mp4", speech, w, h, fps, dur)
        scene = Scene.from_video(0, str(avatar), duration_s=dur, audio_uri=str(speech))
        suffix = ".mp4"
    else:
        scene = Scene.simple(0, (36, 40, 58), "TALKING HEAD", duration_s=dur)
        suffix = ".avi"
    timeline = new_timeline([scene], title="Music Engine demo", width=w, height=h, fps=fps)

    # 4) Caption Track (native) -> narration windows drive ducking.
    timeline = dataclasses.replace(timeline, caption_tracks=(_caption_track(),))

    # 5) Branding + 6) Visual Assets (native tracks) — the full pipeline.
    if not args.no_overlays:
        branding = BrandingEngine().generate(
            reel_duration_s=dur, theme="modern", logo_path=default_logo_path(),
            creator="Alex Rivera", channel="Daily Insights")
        img = generate_image(out_dir / "broll.png", width=1280, height=720,
                             color=(30, 90, 150), label="B-ROLL")
        specs = [AssetSpec(str(img), 3.5, 6.5, kind="image", layout="picture_in_picture",
                           clip_id="broll-0"),
                 AssetSpec(str(img), 11.0, 15.0, kind="image", layout="full_screen",
                           clip_id="broll-1")]
        assets = AssetEngine().build(specs)
        timeline = dataclasses.replace(timeline, branding=branding, asset_tracks=(assets,))

    # 7) MUSIC TRACK — a background bed mixed under the voice (scene-aware fades).
    music = MusicEngine().generate_for_timeline(
        timeline, soundtrack=args.soundtrack, sample_rate=sr, asset_dir=out_dir)
    timeline = dataclasses.replace(timeline, music_tracks=(music,))

    (out_dir / "project.json").write_text(timeline_to_json(timeline), encoding="utf-8")
    c = music.clips[0]
    print(f"Soundtrack      : {args.soundtrack}  gain={c.gain}  "
          f"fade={c.fade.fade_in_s}/{c.fade.fade_out_s}s  loop={c.loop.enabled}  "
          f"duck={c.ducking.enabled}@{c.ducking.duck_level}")
    print(f"Timeline        : {timeline.n_scenes} scene(s), {timeline.duration_s:.2f}s, "
          f"music={timeline.has_music} captions={timeline.has_captions} "
          f"branding={timeline.has_branding} assets={timeline.has_assets}")

    problems: list[str] = []
    if validate_timeline(timeline):
        print("FAIL: timeline invalid:\n  " + "\n  ".join(validate_timeline(timeline)))
        return 3

    # ---- backend-independent mix verification (the audio the renderer muxes) ----
    checks, peak = _verify_mix(timeline, sr)
    # determinism: the identical timeline mixes byte-for-byte the same.
    checks["deterministic mix (byte-identical)"] = (
        mix_timeline_audio(timeline, sr).samples == mix_timeline_audio(timeline, sr).samples)
    print(f"Mix             : peak={peak:.3f} (headroom OK)")
    print("Mix checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"mix check failed: {name}")

    # 8) Render master (voice+music mixed) + exports.
    render_cfg = ReelEngineConfig(render=RenderConfig(
        width=w, height=h, fps=fps, renderer=args.renderer, audio_sample_rate=sr))
    result = get_renderer(args.renderer, render_cfg).render(RenderRequest(
        timeline=timeline, output_path=out_dir / f"music_reel{suffix}",
        renderer=args.renderer, export_profiles=DEMO_PROFILES))
    print(f"Master          : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s, "
          f"music={result.metadata.get('music')})")

    if args.renderer == "ffmpeg":
        m = probe_media(result.output_path)
        if not (m.readable and m.has_audio and (m.width, m.height) == (w, h)):
            problems.append(f"master not playable/correct: {m.width}x{m.height} audio={m.has_audio}")
        if not result.metadata.get("music"):
            problems.append("music was not mixed into the master")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s audio={pe.has_audio}  {'OK' if pe.readable else 'BAD'}")
            if not (pe.readable and pe.has_audio):
                problems.append(f"export {ex.profile} not playable/no audio")
            if (pe.width, pe.height) != _EXPORT_DIMS[ex.profile]:
                problems.append(f"export {ex.profile} wrong aspect: {pe.width}x{pe.height}")
    else:
        f = to_float(read_wav(result.audio_path).samples)
        if len(f) != round(dur * sr):
            problems.append("mock mix sidecar wrong length")
        for ex in result.exports:
            print(f"  export {ex.profile:14} {ex.width}x{ex.height} {ex.aspect} (proxy)")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Music & Audio Mixing Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
