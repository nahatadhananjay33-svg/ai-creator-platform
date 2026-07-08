"""Mock renderer (Phase C2) — hermetic, deterministic, zero external deps.

Generates a *complete* reel from placeholder assets only — solid-colour
backgrounds, a title-card placeholder band per text scene, a silent WAV bed, and
an SRT caption sidecar — using nothing but the stdlib video/audio writers in
``foundation.shared_utils``. No FFmpeg, no AI, no Voice/Avatar engine.

To stay tiny and fast (raw BGR24 is uncompressed), the master is written at a
**proxy resolution** whose longest side is capped by ``render.mock_max_dim``
while the target *aspect ratio* is preserved exactly. This is the structural
proof of the Timeline→frames→file→export pipeline; the FFmpeg renderer produces
the full-resolution, legible-text MP4. Same Timeline ⇒ byte-identical output.
"""
from __future__ import annotations

from array import array
from pathlib import Path

from foundation.shared_utils import Stopwatch, WavData, write_wav
from foundation.shared_utils.video_io import VideoFrames, write_raw_avi
from reel_engine.exporters.profiles import fit_box, get_profile
from reel_engine.interfaces.types import (
    ExportOutput,
    RenderRequest,
    RenderResult,
    Scene,
)
from reel_engine.render.base import TimelineRenderer, proxy_dimensions, scene_frame_count
from reel_engine.render.colors import rgb_to_bgr_bytes, rgb_tuple
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.validate import validate_or_raise

_WHITE = bytes((255, 255, 255))
_BLACK = bytes((0, 0, 0))


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class MockRenderer(TimelineRenderer):
    """Deterministic placeholder renderer producing a raw-AVI reel + sidecars."""

    name = "mock"

    def _scene_frame(self, scene: Scene, w: int, h: int) -> bytes:
        """One BGR24 frame: solid background + a centred title-card band if the
        scene has text (a deterministic placeholder for the real drawtext card)."""
        px = rgb_to_bgr_bytes(scene.background_color())
        frame = bytearray(px * (w * h))
        texts = scene.text_clips()
        if texts:
            text = texts[0].text or ""
            band_h = max(2, h // 8)
            band_w = min(w - 2, max(6, (len(text) * w) // 24))
            y0 = (h - band_h) // 2
            x0 = (w - band_w) // 2
            for y in range(y0, y0 + band_h):
                row = y * w * 3
                for x in range(x0, x0 + band_w):
                    frame[row + x * 3: row + x * 3 + 3] = _WHITE
        return bytes(frame)

    @staticmethod
    def _scale_pad(src: bytes, sw: int, sh: int, profile_name: str) -> tuple:
        """Nearest-neighbour scale + centre-pad one frame into an export profile.
        Shares :func:`fit_box` with the FFmpeg renderer's scale+pad filter."""
        prof = get_profile(profile_name)
        # keep the export a proxy too, at the same longest-side budget as master
        dst_w, dst_h = proxy_dimensions(prof.width, prof.height, max(sw, sh))
        box = fit_box(sw, sh, dst_w, dst_h, mode=prof.fit)
        dst = bytearray(_BLACK * (dst_w * dst_h))
        for y in range(box.scaled_h):
            sy = min(sh - 1, y * sh // box.scaled_h)
            for x in range(box.scaled_w):
                sx = min(sw - 1, x * sw // box.scaled_w)
                spx = src[(sy * sw + sx) * 3:(sy * sw + sx) * 3 + 3]
                dx, dy = box.pad_x + x, box.pad_y + y
                dst[(dy * dst_w + dx) * 3:(dy * dst_w + dx) * 3 + 3] = spx
        return bytes(dst), dst_w, dst_h, prof

    def _write_silent_audio(self, path: Path, duration_s: float) -> Path:
        sr = self.config.render.audio_sample_rate
        n = int(round(duration_s * sr))
        write_wav(path, WavData(samples=array("h", bytes(2 * n)), sample_rate=sr, channels=1))
        return path

    def _write_captions(self, path: Path, timeline) -> Path:
        lines: list[str] = []
        t0 = 0.0
        idx = 1
        for scene in timeline.scenes:
            texts = scene.text_clips()
            if texts and texts[0].text:
                lines += [str(idx),
                          f"{_srt_timestamp(t0)} --> {_srt_timestamp(t0 + scene.duration_s)}",
                          texts[0].text, ""]
                idx += 1
            t0 += scene.duration_s
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def render(self, request: RenderRequest) -> RenderResult:
        tl = validate_or_raise(request.timeline)
        fps = tl.meta.fps
        w, h = proxy_dimensions(tl.meta.width, tl.meta.height, self.config.render.mock_max_dim)
        out = Path(request.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        with Stopwatch() as sw:
            # Build per-scene unique frames once, then repeat by frame count.
            per_scene = [(self._scene_frame(s, w, h), scene_frame_count(s.duration_s, fps))
                         for s in tl.scenes]
            frames: list[bytes] = []
            for frame, count in per_scene:
                frames.extend([frame] * count)
            write_raw_avi(out, VideoFrames(frames=frames, width=w, height=h, fps=float(fps)))

            audio_path = self._write_silent_audio(out.with_suffix(".wav"), tl.duration_s)
            captions_path = self._write_captions(out.with_suffix(".srt"), tl)

            exports = []
            for name in request.export_profiles:
                scaled_cache: dict[int, tuple] = {}
                ex_frames: list[bytes] = []
                ew = eh = 0
                prof = None
                for i, (frame, count) in enumerate(per_scene):
                    if i not in scaled_cache:
                        scaled_cache[i] = self._scale_pad(frame, w, h, name)
                    sframe, ew, eh, prof = scaled_cache[i]
                    ex_frames.extend([sframe] * count)
                ex_path = out.with_name(f"{out.stem}__{name}{out.suffix}")
                write_raw_avi(ex_path, VideoFrames(ex_frames, ew, eh, float(fps)))
                exports.append(ExportOutput(profile=name, path=ex_path,
                                            width=ew, height=eh, aspect=prof.aspect))
        return RenderResult(
            output_path=out, width=w, height=h, fps=float(fps),
            duration_s=tl.duration_s, n_scenes=tl.n_scenes, renderer=self.name,
            render_time_s=round(sw.elapsed_s, 4), timeline_hash=timeline_content_hash(tl),
            exports=tuple(exports), audio_path=audio_path, captions_path=captions_path,
            metadata={"proxy": True, "base_resolution": [tl.meta.width, tl.meta.height],
                      "total_frames": len(frames)},
        )
