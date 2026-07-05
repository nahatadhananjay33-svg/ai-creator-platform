"""Real-time pipeline: text to paced PCM chunks for live voice AI.

Text -> pronunciation -> emotion -> streaming synthesis -> (resampled)
chunks. This is the path phone/WhatsApp agents and Pipecat consume; the
Streaming Manager decides native-vs-fallback streaming per engine.
"""
from __future__ import annotations

from dataclasses import replace
from typing import AsyncIterator, Iterator

from foundation.logging import get_logger
from voice_engine.emotion import EmotionManager
from voice_engine.interfaces import AudioChunk, SynthesisRequest, TTSEngine
from voice_engine.pronunciation import PronunciationManager
from voice_engine.streaming import StreamingManager

logger = get_logger("voice_engine.pipelines.realtime")


class RealTimePipeline:
    """Composes the text front-end with chunked streaming synthesis."""

    def __init__(
        self,
        streaming_manager: StreamingManager,
        pronunciation: PronunciationManager | None = None,
        emotions: EmotionManager | None = None,
    ) -> None:
        self.streaming_manager = streaming_manager
        self.pronunciation = pronunciation
        self.emotions = emotions

    def prepare(self, engine: TTSEngine, request: SynthesisRequest) -> SynthesisRequest:
        """Apply the text front-end (pronunciation, emotion) to a request."""
        if self.pronunciation is not None:
            request = replace(
                request, text=self.pronunciation.apply(request.text, request.language)
            )
        if self.emotions is not None:
            request = self.emotions.apply(request, engine)
        return request

    def stream(self, engine: TTSEngine, request: SynthesisRequest) -> Iterator[AudioChunk]:
        yield from self.streaming_manager.stream(engine, self.prepare(engine, request))

    async def astream(
        self, engine: TTSEngine, request: SynthesisRequest
    ) -> AsyncIterator[AudioChunk]:
        async for chunk in self.streaming_manager.astream(engine, self.prepare(engine, request)):
            yield chunk
