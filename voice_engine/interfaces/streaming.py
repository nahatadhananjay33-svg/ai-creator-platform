"""Streaming synthesis interface for real-time voice AI (Pipecat, telephony)."""
from __future__ import annotations

from abc import abstractmethod
from typing import AsyncIterator, Iterator

from voice_engine.interfaces.tts_engine import TTSEngine
from voice_engine.interfaces.types import AudioChunk, SynthesisRequest


class StreamingTTSEngine(TTSEngine):
    """TTS engine that can emit audio incrementally.

    Contract for real-time use:
    - The first chunk should arrive as fast as the engine allows; the
      benchmark records ``first_chunk_latency_s``.
    - ``stream_synthesize`` must be interruptible: callers stop consuming the
      iterator on barge-in, and the engine must abort generation promptly
      (no runaway GPU work after the consumer disconnects).
    """

    @abstractmethod
    def stream_synthesize(self, request: SynthesisRequest) -> Iterator[AudioChunk]:
        """Yield PCM chunks as they are generated (blocking iterator)."""

    async def astream_synthesize(self, request: SynthesisRequest) -> AsyncIterator[AudioChunk]:
        """Async wrapper; engines with native async I/O should override.

        Default implementation drives the blocking iterator on a worker
        thread so async pipelines (Pipecat) can consume any streaming engine.
        """
        import asyncio

        loop = asyncio.get_running_loop()
        iterator = self.stream_synthesize(request)
        sentinel = object()
        while True:
            chunk = await loop.run_in_executor(None, next, iterator, sentinel)
            if chunk is sentinel:
                break
            yield chunk  # type: ignore[misc]
