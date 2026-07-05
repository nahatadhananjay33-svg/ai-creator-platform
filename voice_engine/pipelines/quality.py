"""Quality pipeline: long-form narration from utterance-scale engines.

Text -> pronunciation -> per-sentence synthesis -> crossfade concatenation
-> peak normalization -> WAV. Turns engines validated on single utterances
(Chatterbox, F5-lineage) into narration engines for reels, YouTube videos,
and avatar scripts, exactly as scoped in the Phase A2 roadmap.
"""
from __future__ import annotations

import array
import tempfile
from dataclasses import replace
from pathlib import Path

from foundation.exceptions import ModelError
from foundation.logging import get_logger
from foundation.shared_utils import (
    Stopwatch,
    WavData,
    read_wav,
    short_hash,
    split_sentences,
    write_wav,
)
from voice_engine.interfaces import SynthesisRequest, SynthesisResult, TTSEngine
from voice_engine.pipelines.audio_export import normalize_peak
from voice_engine.streaming.pcm import resample, to_mono

logger = get_logger("voice_engine.pipelines.quality")


def crossfade_concat(segments: list[WavData], crossfade_ms: int = 30) -> WavData:
    """Concatenate mono segments with a linear crossfade at each join."""
    if not segments:
        raise ModelError("Cannot concatenate zero audio segments")
    rate = segments[0].sample_rate
    normalized = [
        resample(seg, rate) if seg.sample_rate != rate else to_mono(seg) for seg in segments
    ]
    fade = int(rate * crossfade_ms / 1000)
    out = array.array("h", normalized[0].samples)
    for seg in normalized[1:]:
        overlap = min(fade, len(out), len(seg.samples))
        for i in range(overlap):
            a = out[len(out) - overlap + i]
            b = seg.samples[i]
            t = (i + 1) / (overlap + 1)
            out[len(out) - overlap + i] = int(a * (1.0 - t) + b * t)
        out.extend(seg.samples[overlap:])
    return WavData(samples=out, sample_rate=rate, channels=1)


class QualityPipeline:
    """Chunked long-form synthesis with seamless joins."""

    def __init__(
        self,
        max_chunk_chars: int = 300,
        crossfade_ms: int = 30,
        peak_dbfs: float | None = -1.0,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.crossfade_ms = crossfade_ms
        self.peak_dbfs = peak_dbfs

    def run(self, engine: TTSEngine, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize ``request`` chunk-by-chunk and return one joined result.

        The request's text must already have pronunciation/emotion applied —
        this pipeline only owns chunking and audio post-processing.
        """
        sentences = split_sentences(request.text, max_chars=self.max_chunk_chars)
        if not sentences:
            raise ModelError("Quality pipeline received empty text", engine=engine.engine_id)
        logger.info(
            "Quality pipeline starting",
            extra={"context": {"engine": engine.engine_id, "chunks": len(sentences)}},
        )
        segments: list[WavData] = []
        synthesis_time = 0.0
        with Stopwatch() as sw:
            for sentence in sentences:
                result = engine.synthesize(replace(request, text=sentence, output_path=None))
                synthesis_time += result.synthesis_time_s
                segments.append(read_wav(result.audio_path))
            joined = crossfade_concat(segments, self.crossfade_ms)
            if self.peak_dbfs is not None:
                joined = normalize_peak(joined, self.peak_dbfs)
            output_path = request.output_path or self._default_output(engine, request)
            write_wav(output_path, joined)
        return SynthesisResult(
            audio_path=output_path,
            sample_rate=joined.sample_rate,
            audio_duration_s=joined.duration_s,
            synthesis_time_s=sw.elapsed_s,
            engine_id=engine.engine_id,
            request_text_chars=len(request.text),
            metadata={
                "pipeline": "quality",
                "chunks": len(sentences),
                "chunk_synthesis_time_s": round(synthesis_time, 3),
                "crossfade_ms": self.crossfade_ms,
            },
        )

    @staticmethod
    def _default_output(engine: TTSEngine, request: SynthesisRequest) -> Path:
        stem = short_hash(f"quality|{engine.engine_id}|{request.language.value}|{request.text}")
        return Path(tempfile.gettempdir()) / "aicp_voice" / engine.engine_id / f"{stem}.wav"
