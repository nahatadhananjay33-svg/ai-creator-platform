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
                      "base_resolution": [tl.meta.width, tl.meta.height]},
        )
