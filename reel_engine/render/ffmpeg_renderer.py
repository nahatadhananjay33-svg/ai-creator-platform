"""Minimal FFmpeg renderer (Phase C2).

Implements ONLY what the walking skeleton needs: a solid-colour background per
scene, a centred text overlay (drawtext), scene concatenation, and per-profile
export. No transitions, effects, PIP, or animation (those are Phase C4). The
filtergraphs are deliberately trivial — one ``lavfi`` colour source + one
``drawtext`` per scene, then a stream-copy concat, then a scale+pad export.

Requires ``ffmpeg``/``ffprobe`` on PATH (the platform provisions them under
``.venvs/_tools/ffmpeg``; this module also finds a system install). The hermetic
tests use the MockRenderer instead; this backend is validated by the demo run.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.logging import get_logger
from foundation.shared_utils import Stopwatch
from foundation.shared_utils.ffmpeg import ensure_ffmpeg_on_path
from reel_engine.exporters.profiles import get_profile
from reel_engine.interfaces.types import ExportOutput, RenderRequest, RenderResult, Scene
from reel_engine.render.base import TimelineRenderer
from reel_engine.render.branding import resolve_branding
from reel_engine.render.captions import (
    LINE_HEIGHT_FACTOR,
    CaptionDraw,
    lower_caption_tracks,
)
from reel_engine.render.colors import rgb_to_hex
from reel_engine.render.probe import probe_media
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.validate import validate_or_raise

logger = get_logger("reel_engine.render.ffmpeg")

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _find_font() -> str | None:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def _escape_drawtext(text: str) -> str:
    """Escape text for a drawtext ``text='...'`` value (walking-skeleton scope:
    handles the common cases; complex punctuation is a later-phase concern)."""
    return (text.replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "\\'").replace("%", "\\%"))


class FFmpegRenderer(TimelineRenderer):
    """Renders a Timeline to a real, playable MP4 via simple FFmpeg graphs."""

    name = "ffmpeg"

    def __init__(self, config=None) -> None:
        super().__init__(config)
        ensure_ffmpeg_on_path()
        self._ffmpeg = shutil.which("ffmpeg")
        self._font = _find_font()

    # --------------------------------------------------------------- helpers
    def _run(self, args: list[str]) -> None:
        proc = subprocess.run([self._ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *args],
                              capture_output=True, text=True)
        if proc.returncode != 0:
            raise PlatformError(f"ffmpeg failed: {proc.stderr[-500:]}",
                                cmd=" ".join(args[:8]) + " ...")

    def _scene_filter(self, scene: Scene) -> str | None:
        r = self.config.render
        texts = scene.text_clips()
        if not texts or not texts[0].text:
            return None
        if self._font is None:
            logger.warning("No font found; rendering scene without text overlay",
                           extra={"context": {"scene": scene.scene_id}})
            return None
        text = _escape_drawtext(texts[0].text)
        return (
            f"drawtext=fontfile='{self._font}':text='{text}':fontcolor={r.text_color}:"
            f"fontsize={r.font_size}:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"box=1:boxcolor=black@0.35:boxborderw=24"
        )

    def _render_video_scene(self, scene: Scene, meta, out: Path, vclip) -> None:
        """Render a scene whose frame comes from a real media file (C3).

        The footage is fitted into the master frame with the same scale+pad math
        the export path uses (letterbox, never distort), forced to the master fps
        and even dimensions. Audio comes from the scene's real ``audio_file``
        clip when present (the authoritative Voice Engine WAV) — muxed over the
        footage — otherwise a silent bed, so every scene has a uniform stream
        layout and the stream-copy concat stays valid."""
        r = self.config.render
        video_path = vclip.source.uri
        aclip = scene.audio_file_clip()
        args = ["-i", str(video_path)]
        if aclip is not None and aclip.source is not None:
            args += ["-i", str(aclip.source.uri)]
        else:
            args += ["-f", "lavfi", "-i",
                     f"anullsrc=channel_layout=mono:sample_rate={r.audio_sample_rate}"]
        vf = (f"scale={meta.width}:{meta.height}:force_original_aspect_ratio=decrease,"
              f"pad={meta.width}:{meta.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
              f"setsar=1,fps={meta.fps}")
        args += [
            "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
            "-t", f"{scene.duration_s}", "-c:v", r.codec, "-pix_fmt", r.pix_fmt,
            "-b:v", r.bitrate, "-r", str(meta.fps),
            "-c:a", r.audio_codec, "-ar", str(r.audio_sample_rate), "-ac", "1",
            "-shortest", str(out),
        ]
        self._run(args)

    def _render_scene(self, scene: Scene, meta, out: Path) -> None:
        vclip = scene.video_clip()
        if vclip is not None:
            self._render_video_scene(scene, meta, out, vclip)
            return
        r = self.config.render
        color = rgb_to_hex(scene.background_color())
        args = [
            "-f", "lavfi", "-i",
            f"color=c={color}:s={meta.width}x{meta.height}:r={meta.fps}:d={scene.duration_s}",
            "-f", "lavfi", "-i",
            f"anullsrc=channel_layout=mono:sample_rate={r.audio_sample_rate}",
        ]
        vf = self._scene_filter(scene)
        if vf:
            args += ["-vf", vf]
        args += [
            "-t", f"{scene.duration_s}", "-c:v", r.codec, "-pix_fmt", r.pix_fmt,
            "-b:v", r.bitrate, "-r", str(meta.fps),
            "-c:a", r.audio_codec, "-ar", str(r.audio_sample_rate), "-shortest", str(out),
        ]
        self._run(args)

    # ---------------------------------------------------------- captions (C4)
    def _alpha_expr(self, draw: CaptionDraw) -> str | None:
        """A drawtext ``alpha`` expression for the caption's animation, or None
        (fully opaque). v1 animation is opacity-only — see CAPTION_ENGINE.md."""
        a = draw.animation
        if a.kind == "none":
            return None
        s, e = draw.start_s, draw.end_s
        window = e - s
        d = min(max(a.duration_s, 0.0), window / 2.0 if window > 0 else 0.0)
        if d <= 0:
            return None
        if a.kind == "pop":                       # fast ramp-in, then hold
            return f"if(lt(t,{s + d:.4f}),(t-{s:.4f})/{d:.4f},1)"
        return (                                   # fade: ramp in and out
            f"if(lt(t,{s + d:.4f}),(t-{s:.4f})/{d:.4f},"
            f"if(gt(t,{e - d:.4f}),({e:.4f}-t)/{d:.4f},1))"
        )

    def _drawtext(self, draw: CaptionDraw) -> str:
        """Lower one :class:`CaptionDraw` to a single ``drawtext`` filter.

        Positions use ``h``/``w``/``text_w`` so the same expressions are correct
        at any resolution; commas inside expressions are protected by single
        quotes so the filtergraph parser keeps them intact."""
        st = draw.style
        line_h = st.font_size * LINE_HEIGHT_FACTOR
        block_h = draw.line_count * line_h
        off = draw.line_index * line_h
        mv, mh = st.safe_margin_v, st.safe_margin_h
        if st.position == "bottom":
            y = f"h*{1 - mv:.4f}-{block_h:.2f}+{off:.2f}"
        elif st.position == "top":
            y = f"h*{mv:.4f}+{off:.2f}"
        else:
            y = f"(h-{block_h:.2f})/2+{off:.2f}"
        if draw.x_frac is not None:                # karaoke: explicit centre
            x = f"{draw.x_frac:.5f}*w-text_w/2"
        elif st.alignment == "left":
            x = f"w*{mh:.4f}"
        elif st.alignment == "right":
            x = f"w-text_w-w*{mh:.4f}"
        else:
            x = "(w-text_w)/2"

        parts = [
            f"drawtext=fontfile='{self._font}'",
            f"text='{_escape_drawtext(draw.text)}'",
            f"fontcolor={rgb_to_hex(draw.color)}",
            f"fontsize={st.font_size}",
            f"x={x}", f"y={y}",
        ]
        if st.outline_width > 0:
            parts += [f"borderw={st.outline_width}",
                      f"bordercolor={rgb_to_hex(st.outline_color)}"]
        if st.shadow:
            parts += [f"shadowx={st.shadow_offset}", f"shadowy={st.shadow_offset}",
                      f"shadowcolor={rgb_to_hex(st.shadow_color)}"]
        if st.box:
            parts += ["box=1",
                      f"boxcolor={rgb_to_hex(st.box_color)}@{st.box_opacity}",
                      "boxborderw=16"]
        alpha = self._alpha_expr(draw)
        if alpha:
            parts.append(f"alpha='{alpha}'")
        parts.append(f"enable='between(t,{draw.start_s:.4f},{draw.end_s:.4f})'")
        return ":".join(parts)

    def _apply_captions(self, master: Path, tl) -> bool:
        """Burn every caption track into ``master`` in one drawtext pass.

        No-op when the timeline has no caption tracks. Returns whether captions
        were drawn (False if there is nothing to draw or no font is available)."""
        if not tl.caption_tracks:
            return False
        if self._font is None:
            logger.warning("No font found; caption tracks NOT burned in",
                           extra={"context": {"title": tl.meta.title}})
            return False
        draws = lower_caption_tracks(tl)
        if not draws:
            return False
        vf = ",".join(self._drawtext(d) for d in draws)
        r = self.config.render
        tmp = master.with_name(f"{master.stem}__cap{master.suffix}")
        self._run(["-i", str(master), "-vf", vf, "-c:v", r.codec, "-pix_fmt", r.pix_fmt,
                   "-b:v", r.bitrate, "-c:a", "copy", str(tmp)])
        tmp.replace(master)
        return True

    # ---------------------------------------------------------- branding (C5)
    @staticmethod
    def _enable(el) -> str:
        return f":enable='between(t,{el.start_s:.3f},{el.end_s:.3f})'"

    @staticmethod
    def _overlay_xy(position: str, sh: float, sv: float) -> tuple:
        """(x, y) expressions for the ``overlay`` filter (main W/H, overlay w/h)."""
        if "left" in position:
            x = f"W*{sh:.4f}"
        elif "right" in position:
            x = f"W-w-W*{sh:.4f}"
        else:
            x = "(W-w)/2"
        if "top" in position:
            y = f"H*{sv:.4f}"
        elif "bottom" in position:
            y = f"H-h-H*{sv:.4f}"
        else:
            y = "(H-h)/2"
        return x, y

    def _branding_draw(self, el, meta, sh: float, sv: float) -> str:
        """A drawbox/drawtext chain for one non-image branding element.

        Returns a comma-joined filter (or ``null`` passthrough). Boxes/cards
        always draw so branding is visible even without a font; text layers are
        added only when a font is available."""
        font = self._font
        fill = rgb_to_hex(el.fill_color)
        txt = rgb_to_hex(el.text_color)
        en = self._enable(el)
        H, Wd = meta.height, meta.width
        parts: list[str] = []

        def dt(text, fontsize, x, y, color, alpha=1.0):
            return (f"drawtext=fontfile='{font}':text='{_escape_drawtext(text)}':"
                    f"fontcolor={color}@{alpha:.2f}:fontsize={int(fontsize)}:"
                    f"x={x}:y={y}{en}")

        if el.kind in ("intro", "outro"):
            parts.append(f"drawbox=x=0:y=0:w=iw:h=ih:color={fill}@1.0:t=fill{en}")
            if font:
                title_fs, sub_fs, hd_fs = H * 0.045, H * 0.028, H * 0.024
                parts.append(dt(el.text or "", title_fs, "(w-text_w)/2", "h*0.40", txt))
                if el.subtitle:
                    parts.append(dt(el.subtitle, sub_fs, "(w-text_w)/2",
                                    f"h*0.40+{title_fs * 1.4:.0f}", txt))
                for i, line in enumerate(el.lines):
                    parts.append(dt(line, hd_fs, "(w-text_w)/2",
                                    f"h*0.62+{i * hd_fs * 1.5:.0f}", txt))
        elif el.kind == "lower_third":
            parts.append(f"drawbox=x=0:y=ih*0.72:w=iw:h=ih*0.15:"
                         f"color={fill}@{el.opacity:.2f}:t=fill{en}")
            if font:
                parts.append(dt(el.text or "", H * 0.032, f"w*{sh + 0.02:.4f}", "h*0.735", txt))
                if el.subtitle:
                    parts.append(dt(el.subtitle, H * 0.024, f"w*{sh + 0.02:.4f}", "h*0.80", txt))
        elif el.kind == "logo":                 # text badge (no image source)
            bw = max(2, int(el.scale * Wd))
            from reel_engine.render.branding import anchor_frac
            xf, yf = anchor_frac(el.position, bw / Wd, bw / H, sh, sv)
            x0, y0 = int(xf * Wd), int(yf * H)
            parts.append(f"drawbox=x={x0}:y={y0}:w={bw}:h={bw}:"
                         f"color={fill}@{el.opacity:.2f}:t=fill{en}")
            if font and el.text:
                parts.append(dt(el.text, bw * 0.42, f"{x0}+({bw}-text_w)/2",
                                f"{y0}+({bw}-text_h)/2", txt))
        elif el.kind == "watermark":             # text mark (image handled elsewhere)
            if not (font and el.text):
                return "null"
            x, y = self._text_xy(el.position, sh, sv)
            parts.append(dt(el.text, max(14, Wd * el.scale * 0.35), x, y, txt, alpha=el.opacity))

        return ",".join(parts) if parts else "null"

    @staticmethod
    def _text_xy(position: str, sh: float, sv: float) -> tuple:
        """(x, y) expressions for a ``drawtext`` anchored by ``position``."""
        if "left" in position:
            x = f"w*{sh:.4f}"
        elif "right" in position:
            x = f"w-text_w-w*{sh:.4f}"
        else:
            x = "(w-text_w)/2"
        if "top" in position:
            y = f"h*{sv:.4f}"
        elif "bottom" in position:
            y = f"h-text_h-h*{sv:.4f}"
        else:
            y = "(h-text_h)/2"
        return x, y

    def _apply_branding(self, master: Path, tl) -> bool:
        """Composite the branding track onto ``master`` via one filter_complex.

        Image logos/watermarks are overlaid (scaled + alpha); intro/outro cards,
        lower thirds, text badges and text watermarks are drawn. No-op when the
        timeline has no branding. Returns whether anything was composited."""
        if tl.branding is None or not tl.branding.has_elements:
            return False
        elements = resolve_branding(tl)
        if not elements:
            return False
        meta = tl.meta
        sh, sv = tl.branding.theme.safe_margin_h, tl.branding.theme.safe_margin_v
        inputs: list[str] = ["-i", str(master)]
        prep: list[str] = []
        steps: list[str] = []
        cur = "0:v"
        img_idx = 1
        for n, el in enumerate(elements, start=1):
            out_lbl = f"b{n}"
            if el.kind in ("logo", "watermark") and el.source is not None:
                inputs += ["-i", str(el.source.uri)]
                in_lbl, prep_lbl = f"{img_idx}:v", f"p{img_idx}"
                img_idx += 1
                target_w = max(2, int(el.scale * meta.width))
                prep.append(f"[{in_lbl}]format=rgba,"
                            f"colorchannelmixer=aa={el.opacity:.3f},"
                            f"scale={target_w}:-1[{prep_lbl}]")
                x, y = self._overlay_xy(el.position, sh, sv)
                steps.append(f"[{cur}][{prep_lbl}]overlay={x}:{y}"
                             f"{self._enable(el)}[{out_lbl}]")
            else:
                steps.append(f"[{cur}]{self._branding_draw(el, meta, sh, sv)}[{out_lbl}]")
            cur = out_lbl

        filter_complex = ";".join(prep + steps)
        r = self.config.render
        tmp = master.with_name(f"{master.stem}__brand{master.suffix}")
        self._run([*inputs, "-filter_complex", filter_complex,
                   "-map", f"[{cur}]", "-map", "0:a?",
                   "-c:v", r.codec, "-pix_fmt", r.pix_fmt, "-b:v", r.bitrate,
                   "-c:a", "copy", str(tmp)])
        tmp.replace(master)
        return True

    def _concat(self, scene_files: list[Path], out: Path, work: Path) -> None:
        listfile = work / "concat.txt"
        listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_files),
                            encoding="utf-8")
        self._run(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(out)])

    def _export(self, master: Path, profile_name: str, out: Path) -> ExportOutput:
        prof = get_profile(profile_name)
        r = self.config.render
        vf = (f"scale={prof.width}:{prof.height}:force_original_aspect_ratio=decrease,"
              f"pad={prof.width}:{prof.height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
        self._run(["-i", str(master), "-vf", vf, "-c:v", r.codec, "-pix_fmt", r.pix_fmt,
                   "-b:v", r.bitrate, "-c:a", "copy", str(out)])
        return ExportOutput(profile=profile_name, path=out, width=prof.width,
                            height=prof.height, aspect=prof.aspect)

    def export_master(self, master: Path, profile_names) -> tuple:
        """Fit an already-rendered master into each platform/aspect profile.

        Public so callers (e.g. the end-to-end pipeline) can render a master once
        and time the cheap scale+pad export pass separately from the render pass.
        ``render`` uses this internally, so the two paths stay identical."""
        master = Path(master)
        return tuple(
            self._export(master, name,
                         master.with_name(f"{master.stem}__{name}{master.suffix}"))
            for name in profile_names
        )

    # ----------------------------------------------------------------- render
    def render(self, request: RenderRequest) -> RenderResult:
        if self._ffmpeg is None:
            raise PlatformError("ffmpeg not found on PATH; install FFmpeg or use the mock renderer")
        tl = validate_or_raise(request.timeline)
        out = Path(request.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        work = out.parent / f".{out.stem}_scenes"
        work.mkdir(parents=True, exist_ok=True)

        with Stopwatch() as sw:
            scene_files: list[Path] = []
            for scene in tl.scenes:
                sf = work / f"scene_{scene.index:03d}.mp4"
                self._render_scene(scene, tl.meta, sf)
                scene_files.append(sf)
            self._concat(scene_files, out, work)
            # Captions then branding are native Timeline tracks: composite them
            # into the master BEFORE export so every aspect profile inherits them.
            captions_drawn = self._apply_captions(out, tl)
            branding_drawn = self._apply_branding(out, tl)

            exports = list(self.export_master(out, request.export_profiles))

        # cleanup intermediates (keep master + exports)
        for sf in scene_files:
            sf.unlink(missing_ok=True)
        (work / "concat.txt").unlink(missing_ok=True)
        try:
            work.rmdir()
        except OSError:
            pass

        probe = probe_media(out)
        return RenderResult(
            output_path=out, width=probe.width, height=probe.height, fps=probe.fps,
            duration_s=probe.duration_s, n_scenes=tl.n_scenes, renderer=self.name,
            render_time_s=round(sw.elapsed_s, 4), timeline_hash=timeline_content_hash(tl),
            exports=tuple(exports),
            metadata={"has_text": self._font is not None, "font": self._font,
                      "captions": captions_drawn, "branding": branding_drawn,
                      "base_resolution": [tl.meta.width, tl.meta.height]},
        )
