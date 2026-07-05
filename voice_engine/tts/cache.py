"""Synthesis output caching.

Wraps :class:`foundation.cache.DiskCache`: the WAV artifact is stored next
to the JSON metadata of its :class:`SynthesisResult`, keyed on everything
that changes the audio (engine, voice profile, text, language, speed,
emotion, seed, extra params). Repeated generations of unchanged script
lines (reel re-renders, avatar retakes) become free.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from foundation.cache import DiskCache
from foundation.logging import get_logger
from foundation.shared_utils import short_hash
from voice_engine.interfaces import SynthesisRequest, SynthesisResult

logger = get_logger("voice_engine.tts.cache")

_ARTIFACT_NAME = "audio.wav"


class SynthesisCacheManager:
    """Content-addressed cache of synthesized audio."""

    def __init__(
        self,
        namespace: str = "voice_synthesis",
        root: Path | None = None,
        enabled: bool = True,
    ) -> None:
        self.enabled = enabled
        self._cache = DiskCache(namespace, root=root)

    @staticmethod
    def key_for(request: SynthesisRequest, engine_id: str) -> str:
        """Deterministic key over every request field that shapes the audio."""
        payload = {
            "engine": engine_id,
            "text": request.text,
            "language": request.language.value,
            "voice": request.voice.profile_id if request.voice else None,
            "speed": request.speed,
            "emotion": request.emotion,
            "seed": request.seed,
            "extra": request.extra,
        }
        return short_hash(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str), 24)

    def get(self, request: SynthesisRequest, engine_id: str) -> SynthesisResult | None:
        """Return the cached result, materialized at ``request.output_path`` if set."""
        if not self.enabled:
            return None
        key = self.key_for(request, engine_id)
        meta = self._cache.get(key)
        if meta is None:
            return None
        artifact = self._cache.artifact_path(key, _ARTIFACT_NAME)
        if not artifact.exists():
            self._cache.evict(key)  # metadata without audio is useless
            return None
        audio_path = artifact
        if request.output_path is not None and request.output_path != artifact:
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact, request.output_path)
            audio_path = request.output_path
        logger.debug("Synthesis cache hit", extra={"context": {"engine": engine_id, "key": key}})
        return SynthesisResult(
            audio_path=audio_path,
            sample_rate=int(meta["sample_rate"]),
            audio_duration_s=float(meta["audio_duration_s"]),
            synthesis_time_s=0.0,
            first_chunk_latency_s=None,
            engine_id=engine_id,
            request_text_chars=len(request.text),
            metadata={**meta.get("metadata", {}), "cache_hit": True},
        )

    def put(self, request: SynthesisRequest, engine_id: str, result: SynthesisResult) -> None:
        """Store the result's audio and metadata for future hits."""
        if not self.enabled or not result.audio_path.exists():
            return
        key = self.key_for(request, engine_id)
        artifact = self._cache.artifact_path(key, _ARTIFACT_NAME)
        if result.audio_path != artifact:
            shutil.copyfile(result.audio_path, artifact)
        self._cache.put(
            key,
            {
                "sample_rate": result.sample_rate,
                "audio_duration_s": result.audio_duration_s,
                "synthesis_time_s": result.synthesis_time_s,
                "metadata": result.metadata,
            },
        )

    def evict(self, request: SynthesisRequest, engine_id: str) -> bool:
        return self._cache.evict(self.key_for(request, engine_id))

    def clear(self) -> None:
        self._cache.clear()
