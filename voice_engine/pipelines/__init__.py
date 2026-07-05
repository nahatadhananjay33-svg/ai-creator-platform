"""End-to-end voice pipelines: text -> pronunciation -> synthesis ->
post-processing -> export.

- :class:`QualityPipeline`: chunked long-form narration (reels, YouTube).
- :class:`RealTimePipeline`: paced PCM chunk streaming (voice AI).
- :class:`AudioExportManager`: WAV/MP3/OGG/FLAC delivery formats.
"""

from voice_engine.pipelines.audio_export import AudioExportManager, normalize_peak
from voice_engine.pipelines.quality import QualityPipeline, crossfade_concat
from voice_engine.pipelines.realtime import RealTimePipeline

__all__ = [
    "AudioExportManager",
    "QualityPipeline",
    "RealTimePipeline",
    "crossfade_concat",
    "normalize_peak",
]
