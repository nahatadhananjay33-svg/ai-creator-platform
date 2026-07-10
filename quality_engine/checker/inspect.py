"""Deterministic media probing (Phase C16) — read the reel's actual files.

``inspect_reel`` turns a :class:`~quality_engine.checker.model.ReelArtifacts` into
a measured :class:`~quality_engine.checker.model.ReelInspection` by reading the
files on disk. It uses only:

- the stdlib raw-AVI / WAV readers (:func:`read_raw_avi`, :func:`read_wav`) — the
  hermetic path the mock renderer's output takes (no ffmpeg, no numpy); and
- the existing ``ffprobe`` wrapper (:func:`probe_media`) — the fallback for real
  MP4s, only reached when the master is not a stdlib-readable raw-AVI.

So the whole hermetic test suite runs with zero external tools, while a real MP4
still gets probed correctly. Probing never raises to the caller: any failure is
captured into ``ReelInspection.errors`` and surfaces as a failed check.
"""
from __future__ import annotations

from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.shared_utils.audio_io import read_wav
from foundation.shared_utils.video_io import read_raw_avi

from reel_engine.exporters.profiles import get_profile
from reel_engine.interfaces.types import aspect_ratio_string

from quality_engine.checker.model import ExportProbe, ReelArtifacts, ReelInspection


def _count_srt_cues(path: Path) -> int:
    """Number of subtitle cues in an SRT file (blocks separated by blank lines)."""
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return 0
    return sum(1 for block in text.split("\n\n") if block.strip())


def inspect_reel(artifacts: ReelArtifacts) -> ReelInspection:
    """Probe a reel's master + sidecars + exports into measured facts."""
    errors: list[str] = []
    master = Path(artifacts.master_path)

    # ---- master video --------------------------------------------------------
    master_exists = master.exists()
    readable = False
    width = height = n_frames = 0
    fps = video_duration = 0.0
    muxed_audio = False
    if not master_exists:
        errors.append(f"master missing: {master}")
    else:
        try:  # the mock proxy is a stdlib-readable raw-AVI (no external tools)
            v = read_raw_avi(master)
            readable = v.n_frames > 0 and v.width > 0 and v.height > 0
            width, height, fps = v.width, v.height, v.fps
            n_frames, video_duration = v.n_frames, v.duration_s
        except PlatformError:
            try:  # a real codec (MP4) -> ffprobe
                from reel_engine.render import probe_media
                m = probe_media(master)
                readable, width, height, fps = m.readable, m.width, m.height, m.fps
                n_frames, video_duration = m.n_frames, m.duration_s
                muxed_audio = m.has_audio
            except Exception as exc:  # noqa: BLE001 - unreadable => a failed check
                errors.append(f"master unreadable: {exc}")

    # ---- audio ---------------------------------------------------------------
    audio_source = "none"
    audio_present = False
    audio_duration: float | None = None
    audio_silent = False
    sidecar = artifacts.audio_path
    if sidecar is None and master_exists:  # ffmpeg emits no sidecar; try the mock's
        candidate = master.with_suffix(".wav")
        sidecar = candidate if candidate.exists() else None
    if sidecar is not None and Path(sidecar).exists():
        try:
            wav = read_wav(sidecar)
            audio_source, audio_present = "sidecar", True
            audio_duration = wav.duration_s
            audio_silent = not any(wav.samples)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"audio sidecar unreadable: {exc}")
    elif muxed_audio:
        audio_source, audio_present = "muxed", True
        audio_duration = video_duration  # muxed => same container timeline

    # ---- captions sidecar ----------------------------------------------------
    captions_exists = False
    n_cues = 0
    captions = artifacts.captions_path
    if captions is None and master_exists:
        candidate = master.with_suffix(".srt")
        captions = candidate if candidate.exists() else None
    if captions is not None and Path(captions).exists():
        captions_exists = True
        try:
            n_cues = _count_srt_cues(Path(captions))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"captions sidecar unreadable: {exc}")

    # ---- exports -------------------------------------------------------------
    export_probes: list[ExportProbe] = []
    for ex in artifacts.exports:
        p = Path(ex.path)
        exists = p.exists()
        try:
            expected = get_profile(ex.profile).aspect
        except KeyError:
            expected = ""
        aspect = ex.aspect or (aspect_ratio_string(ex.width, ex.height) if ex.width else "")
        export_probes.append(ExportProbe(
            profile=ex.profile, path=p, exists=exists, width=ex.width,
            height=ex.height, aspect=aspect, expected_aspect=expected))

    return ReelInspection(
        master_exists=master_exists, video_readable=readable, width=width,
        height=height, fps=fps, n_frames=n_frames, video_duration_s=video_duration,
        audio_source=audio_source, audio_present=audio_present,
        audio_duration_s=audio_duration, audio_silent=audio_silent,
        captions_sidecar_exists=captions_exists, n_caption_cues=n_cues,
        exports=tuple(export_probes), errors=tuple(errors),
    )
