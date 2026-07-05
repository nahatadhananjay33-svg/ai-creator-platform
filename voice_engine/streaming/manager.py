"""Streaming Manager: uniform chunked audio from any engine.

Two paths behind one iterator API:

- **Native**: engines implementing :class:`StreamingTTSEngine` stream
  directly; chunks are optionally resampled to the configured rate.
- **Fallback**: any other engine is driven sentence-by-sentence — each
  sentence is synthesized as a unit and sliced into chunks. First-chunk
  latency is then one sentence's synthesis time, which is workable for
  engines with RTF < 1 (Kokoro/MeloTTS per Phase A1.5).

Barge-in: consumers simply stop iterating (or ``close()`` the generator);
no further synthesis work is scheduled after that.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import AsyncIterator, Iterator

from foundation.logging import get_logger
from foundation.shared_utils import read_wav, split_sentences
from voice_engine.interfaces import AudioChunk, StreamingTTSEngine, SynthesisRequest, TTSEngine
from voice_engine.streaming.pcm import resample, resample_pcm_bytes, wav_to_chunks
from voice_engine.tts.config import StreamingConfig

logger = get_logger("voice_engine.streaming")


class StreamingManager:
    """Streams synthesis output as PCM chunks from native or fallback engines."""

    def __init__(self, config: StreamingConfig | None = None) -> None:
        self.config = config or StreamingConfig()

    def stream(self, engine: TTSEngine, request: SynthesisRequest) -> Iterator[AudioChunk]:
        """Yield PCM chunks for ``request`` using the best path for ``engine``."""
        if isinstance(engine, StreamingTTSEngine):
            yield from self._stream_native(engine, request)
        else:
            yield from self._stream_fallback(engine, request)

    async def astream(
        self, engine: TTSEngine, request: SynthesisRequest
    ) -> AsyncIterator[AudioChunk]:
        """Async variant driving the blocking iterator on a worker thread."""
        loop = asyncio.get_running_loop()
        iterator = self.stream(engine, request)
        sentinel = object()
        try:
            while True:
                chunk = await loop.run_in_executor(None, next, iterator, sentinel)
                if chunk is sentinel:
                    break
                yield chunk  # type: ignore[misc]
        finally:
            iterator.close()

    # ------------------------------------------------------------------ paths
    def _stream_native(
        self, engine: StreamingTTSEngine, request: SynthesisRequest
    ) -> Iterator[AudioChunk]:
        target = self.config.sample_rate
        for chunk in engine.stream_synthesize(request):
            if target is None or chunk.sample_rate == target:
                yield chunk
            else:
                yield AudioChunk(
                    pcm_s16le=resample_pcm_bytes(chunk.pcm_s16le, chunk.sample_rate, target),
                    sample_rate=target,
                    chunk_index=chunk.chunk_index,
                    is_final=chunk.is_final,
                )

    def _stream_fallback(
        self, engine: TTSEngine, request: SynthesisRequest
    ) -> Iterator[AudioChunk]:
        sentences = split_sentences(request.text, max_chars=self.config.max_sentence_chars)
        if not sentences:
            return
        logger.debug(
            "Fallback sentence-chunked streaming",
            extra={"context": {"engine": engine.engine_id, "sentences": len(sentences)}},
        )
        next_index = 0
        for pos, sentence in enumerate(sentences):
            piece = replace(request, text=sentence, output_path=None)
            result = engine.synthesize(piece)
            wav = read_wav(result.audio_path)
            if self.config.sample_rate is not None:
                wav = resample(wav, self.config.sample_rate)
            chunks = wav_to_chunks(
                wav,
                chunk_ms=self.config.chunk_ms,
                start_index=next_index,
                final=pos == len(sentences) - 1,
            )
            next_index += len(chunks)
            yield from chunks
