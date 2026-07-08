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
from reel_engine.render.branding import anchor_frac, resolve_branding
from reel_engine.render.captions import CaptionDraw, caption_alpha, lower_caption_tracks
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
        """SRT sidecar. Prefers the native caption track (C4); falls back to
        per-scene text (C2 timelines with no caption tracks)."""
        lines: list[str] = []
        if timeline.caption_tracks:
            for idx, seg in enumerate(timeline.caption_tracks[0].segments, start=1):
                lines += [str(idx),
                          f"{_srt_timestamp(seg.start_s)} --> {_srt_timestamp(seg.end_s)}",
                          seg.text, ""]
        else:
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

    # ---------------------------------------------------------- captions (C4)
    def _caption_box(self, draw: CaptionDraw, w: int, h: int) -> tuple:
        """Deterministic (x0, x1, y0, y1) band for a caption on the proxy frame.

        The mock has no font engine, so a caption is a solid band placed by the
        style's position/alignment/safe margins and sized from the text length —
        enough for hermetic tests to assert *where*, *when*, and *what colour* a
        caption is, matching what FFmpeg's drawtext lowers to."""
        st = draw.style
        line_h = max(1, h // 10)
        block_h = draw.line_count * line_h
        if st.position == "bottom":
            block_top = int(h * (1 - st.safe_margin_v)) - block_h
        elif st.position == "top":
            block_top = int(h * st.safe_margin_v)
        else:
            block_top = (h - block_h) // 2
        y0 = block_top + draw.line_index * line_h
        y1 = y0 + line_h

        denom = st.max_chars_per_line or 40
        frac = min(1.0, max(1, len(draw.text)) / denom)
        band_w = max(2, int(frac * w * 0.8))
        if draw.x_frac is not None:
            cx = draw.x_frac * w
        elif st.alignment == "left":
            cx = w * st.safe_margin_h + band_w / 2
        elif st.alignment == "right":
            cx = w - w * st.safe_margin_h - band_w / 2
        else:
            cx = w / 2.0
        x0 = int(cx - band_w / 2)
        x1 = x0 + band_w
        x0 = max(0, min(x0, w - 1))
        x1 = max(x0 + 1, min(x1, w))
        y0 = max(0, min(y0, h - 1))
        y1 = max(y0 + 1, min(y1, h))
        return x0, x1, y0, y1

    def _paint_captions(self, base: bytes, w: int, h: int, active: list) -> bytes:
        """Paint the active caption bands onto a copy of ``base`` (BGR24)."""
        frame = bytearray(base)
        for draw, alpha in sorted(active, key=lambda da: da[0].layer):
            x0, x1, y0, y1 = self._caption_box(draw, w, h)
            bgr = rgb_to_bgr_bytes(draw.color)
            for y in range(y0, y1):
                row = y * w * 3
                for x in range(x0, x1):
                    o = row + x * 3
                    if alpha >= 0.999:
                        frame[o:o + 3] = bgr
                    else:
                        for k in range(3):
                            frame[o + k] = int(round(frame[o + k] * (1 - alpha)
                                                     + bgr[k] * alpha))
        return bytes(frame)

    def _overlay_captions(self, base_frames: list, w: int, h: int, fps: int,
                          timeline) -> list:
        """Return a frame list with caption tracks overlaid at absolute time.

        Frames with no active caption pass through untouched; painted frames are
        cached by (base-frame identity, active draws + rounded alpha) so the pass
        stays fast and byte-for-byte deterministic."""
        draws = lower_caption_tracks(timeline)
        if not draws:
            return base_frames
        out: list = []
        cache: dict = {}
        for idx, base in enumerate(base_frames):
            t = idx / fps
            active = [(d, caption_alpha(d.animation, d.start_s, d.end_s, t))
                      for d in draws if d.start_s - 1e-9 <= t <= d.end_s + 1e-9]
            active = [(d, a) for d, a in active if a > 0.01]
            if not active:
                out.append(base)
                continue
            sig = (id(base), tuple((id(d), round(a, 3)) for d, a in active))
            painted = cache.get(sig)
            if painted is None:
                painted = self._paint_captions(base, w, h, active)
                cache[sig] = painted
            out.append(painted)
        return out

    # ---------------------------------------------------------- branding (C5)
    def _branding_box(self, el, w: int, h: int, safe_h: float, safe_v: float) -> tuple:
        """Deterministic (x0, x1, y0, y1) box for a branding element.

        The mock has no font/image engine, so each element is a solid box placed
        by the same position + safe-margin rules the FFmpeg backend lowers to —
        enough to assert *where*, *when*, and *what colour* branding is, and to
        keep the hermetic suite byte-for-byte reproducible."""
        if el.full_frame:
            return 0, w, 0, h
        if el.kind == "lower_third":
            box_w = int(w * (1 - 2 * safe_h))
            box_h = max(2, int(h * 0.14))
            x0, y0 = int(w * safe_h), int(h * (1 - safe_v - 0.14))
            return x0, x0 + box_w, y0, min(h, y0 + box_h)
        # logo (square) / watermark (wide-ish)
        box_w = max(2, int(el.scale * w))
        box_h = box_w if el.kind == "logo" else max(2, int(0.45 * box_w))
        xf, yf = anchor_frac(el.position, box_w / w, box_h / h, safe_h, safe_v)
        x0, y0 = int(xf * w), int(yf * h)
        return x0, min(w, x0 + box_w), y0, min(h, y0 + box_h)

    def _overlay_branding(self, frames: list, w: int, h: int, fps: int,
                          timeline) -> list:
        """Return a frame list with branding overlaid at absolute reel time."""
        elements = resolve_branding(timeline)
        if not elements:
            return frames
        theme = timeline.branding.theme
        sh, sv = theme.safe_margin_h, theme.safe_margin_v
        out: list = []
        cache: dict = {}
        for idx, base in enumerate(frames):
            t = idx / fps
            active = [el for el in elements if el.start_s - 1e-9 <= t <= el.end_s + 1e-9]
            if not active:
                out.append(base)
                continue
            sig = (id(base), tuple(id(el) for el in active))
            painted = cache.get(sig)
            if painted is None:
                buf = bytearray(base)
                for el in active:                       # already bottom-to-top
                    x0, x1, y0, y1 = self._branding_box(el, w, h, sh, sv)
                    bgr = rgb_to_bgr_bytes(el.fill_color)
                    a = 1.0 if el.full_frame else max(0.0, min(1.0, el.opacity))
                    for y in range(max(0, y0), min(h, y1)):
                        row = y * w * 3
                        for x in range(max(0, x0), min(w, x1)):
                            o = row + x * 3
                            if a >= 0.999:
                                buf[o:o + 3] = bgr
                            else:
                                for k in range(3):
                                    buf[o + k] = int(round(buf[o + k] * (1 - a) + bgr[k] * a))
                painted = bytes(buf)
                cache[sig] = painted
            out.append(painted)
        return out

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
            base_frames: list[bytes] = []
            for frame, count in per_scene:
                base_frames.extend([frame] * count)
            # Captions then branding are native Timeline tracks: overlay them in
            # absolute reel time (branding on top; each a no-op when absent).
            frames = self._overlay_captions(base_frames, w, h, fps, tl)
            frames = self._overlay_branding(frames, w, h, fps, tl)
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
                # Exports inherit captions + branding too (FFmpeg parity).
                ex_frames = self._overlay_captions(ex_frames, ew, eh, fps, tl)
                ex_frames = self._overlay_branding(ex_frames, ew, eh, fps, tl)
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
