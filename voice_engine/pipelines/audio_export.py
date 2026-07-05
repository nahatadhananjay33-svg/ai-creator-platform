"""Audio Export Manager: canonical WAV in, delivery formats out.

WAV export (with optional peak normalization and resampling) is
dependency-free. Compressed formats (MP3/OGG/FLAC) shell out to the
platform-managed FFmpeg (installed by Phase A1.5 under
``.venvs/_tools/ffmpeg``) or any ``ffmpeg`` on PATH.
"""
from __future__ import annotations

import array
import math
import shutil
import subprocess
from pathlib import Path

from foundation.constants import AudioFormat
from foundation.exceptions import PlatformError
from foundation.logging import get_logger
from foundation.shared_utils import WavData, read_wav, write_wav
from voice_engine.scripts import ensure_ffmpeg_on_path
from voice_engine.streaming.pcm import resample, to_mono
from voice_engine.tts.config import ExportConfig

logger = get_logger("voice_engine.pipelines.export")

_FFMPEG_FORMATS = {AudioFormat.MP3, AudioFormat.OGG, AudioFormat.FLAC}


def normalize_peak(wav: WavData, target_dbfs: float = -1.0) -> WavData:
    """Scale samples so the peak sits at ``target_dbfs`` (never amplifies clipping)."""
    if target_dbfs > 0:
        raise PlatformError(f"target_dbfs must be <= 0, got {target_dbfs}")
    peak = max((abs(s) for s in wav.samples), default=0)
    if peak == 0:
        return wav
    target_peak = 32767 * math.pow(10.0, target_dbfs / 20.0)
    gain = target_peak / peak
    scaled = array.array(
        "h", (max(-32768, min(32767, int(s * gain))) for s in wav.samples)
    )
    return WavData(samples=scaled, sample_rate=wav.sample_rate, channels=wav.channels)


class AudioExportManager:
    """Exports synthesized WAV files to delivery formats."""

    def __init__(self, config: ExportConfig | None = None) -> None:
        self.config = config or ExportConfig()

    @staticmethod
    def ffmpeg_available() -> bool:
        ensure_ffmpeg_on_path()
        return shutil.which("ffmpeg") is not None

    def export(
        self,
        source_wav: Path | str,
        output_path: Path | str,
        audio_format: AudioFormat | str | None = None,
        sample_rate: int | None = None,
        peak_dbfs: float | None = None,
    ) -> Path:
        """Export ``source_wav`` to ``output_path``.

        Args:
            audio_format: Target format; defaults to the configured one, or
                is inferred from ``output_path``'s suffix when that is set.
            sample_rate: Optional output sample rate.
            peak_dbfs: Peak-normalization target; defaults to the configured
                value (pass a value explicitly to override; the configured
                ``null`` disables normalization).

        Raises:
            PlatformError: source missing, or FFmpeg needed but not found.
        """
        source = Path(source_wav)
        output = Path(output_path)
        if not source.exists():
            raise PlatformError(f"Export source not found: {source}", path=str(source))
        fmt = self._resolve_format(audio_format, output)
        target_dbfs = self.config.peak_dbfs if peak_dbfs is None else peak_dbfs
        output.parent.mkdir(parents=True, exist_ok=True)

        if fmt is AudioFormat.WAV or fmt is AudioFormat.PCM_S16LE:
            wav = to_mono(read_wav(source))
            if sample_rate is not None and sample_rate != wav.sample_rate:
                wav = resample(wav, sample_rate)
            if target_dbfs is not None:
                wav = normalize_peak(wav, target_dbfs)
            if fmt is AudioFormat.PCM_S16LE:
                output.write_bytes(wav.samples.tobytes())
            else:
                write_wav(output, wav)
        else:
            self._export_via_ffmpeg(source, output, fmt, sample_rate, target_dbfs)
        logger.info(
            "Audio exported",
            extra={"context": {"format": fmt.value, "output": str(output)}},
        )
        return output

    # ------------------------------------------------------------------ internals
    def _resolve_format(
        self, audio_format: AudioFormat | str | None, output: Path
    ) -> AudioFormat:
        if audio_format is not None:
            return AudioFormat(audio_format)
        suffix = output.suffix.lstrip(".").lower()
        if suffix:
            try:
                return AudioFormat(suffix)
            except ValueError:
                raise PlatformError(
                    f"Unsupported export format: .{suffix}",
                    known=[f.value for f in AudioFormat],
                ) from None
        return AudioFormat(self.config.format)

    def _export_via_ffmpeg(
        self,
        source: Path,
        output: Path,
        fmt: AudioFormat,
        sample_rate: int | None,
        peak_dbfs: float | None,
    ) -> None:
        if fmt not in _FFMPEG_FORMATS:
            raise PlatformError(f"No export path for format {fmt.value!r}")
        if not self.ffmpeg_available():
            raise PlatformError(
                f"FFmpeg is required to export {fmt.value} but was not found on PATH; "
                "install it or use WAV export",
                format=fmt.value,
            )
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source)]
        filters: list[str] = []
        if peak_dbfs is not None:
            # Single-pass loudness-safe peak limit; matches normalize_peak intent.
            filters.append(f"alimiter=limit={math.pow(10.0, peak_dbfs / 20.0):.6f}")
        if filters:
            cmd += ["-af", ",".join(filters)]
        if sample_rate is not None:
            cmd += ["-ar", str(sample_rate)]
        cmd.append(str(output))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PlatformError(
                f"FFmpeg export failed for {output.name}",
                returncode=proc.returncode,
                stderr=proc.stderr.strip()[-500:],
            )
