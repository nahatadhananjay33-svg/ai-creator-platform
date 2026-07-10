"""VoiceEngine: the production facade of the voice platform.

Everything outside ``voice_engine`` (reel engine, avatar engine, real-estate
voice AI, the benchmark) talks to this class only::

    from voice_engine import VoiceEngine

    voice = VoiceEngine()                      # config-driven defaults
    voice.load_model("kokoro")                 # or rely on defaults/routing
    profile = voice.clone_voice("ref.wav", "Agent Priya",
                                consent="P. Sharma, 2026-07-04, marketing")
    result = voice.generate("Namaste! Welcome to Capital Greens.",
                            language="hi", voice=profile)
    for chunk in voice.stream("Hello!", language="en"):
        play(chunk.pcm_s16le)
    voice.save_profile(profile)
    profile = voice.load_profile(profile.profile_id)

The facade composes (never reimplements) the platform managers: adapters
(Phase A1), profile store, pronunciation, emotion, streaming, caching,
pipelines, and export. Model choice is configuration (``defaults.yaml`` /
env overrides), not code.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from types import TracebackType
from typing import Any, AsyncIterator, Iterator

from foundation.constants import AudioFormat, Language
from foundation.exceptions import ModelError
from foundation.logging import get_logger
from voice_engine.adapters import (
    ADAPTER_CLASSES,
    available_adapter_ids,
    forget_cached_adapter,
    get_or_create_adapter,
)
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.emotion import EmotionManager, EmotionSpec, resolve_emotion
from voice_engine.interfaces import (
    AudioChunk,
    SynthesisRequest,
    SynthesisResult,
    VoiceProfile,
)
from voice_engine.pipelines import AudioExportManager, QualityPipeline, RealTimePipeline
from voice_engine.pronunciation import PronunciationManager
from voice_engine.streaming import StreamingManager
from voice_engine.tts import (
    EngineRouter,
    SynthesisCacheManager,
    VoiceEngineConfig,
    load_voice_engine_config,
)
from voice_engine.voices import CONSENT_KEY, VoiceProfileManager

logger = get_logger("voice_engine.engine")


class VoiceEngine:
    """High-level, reusable production voice API."""

    def __init__(
        self,
        config: VoiceEngineConfig | None = None,
        config_path: Path | str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> None:
        """Create an engine from layered configuration.

        Args:
            config: Pre-built configuration (wins over the other arguments).
            config_path: Environment YAML overlaying the packaged defaults.
            overrides: Highest-precedence nested overrides.
        """
        self.config = config or load_voice_engine_config(config_path, overrides)
        self.profiles = VoiceProfileManager(
            directory=self.config.profiles.directory,
            require_consent=self.config.profiles.require_consent,
        )
        self.pronunciation = PronunciationManager.from_lexicons(
            self.config.pronunciation.lexicons
        )
        self.emotions = EmotionManager(self.config.emotion.strategies)
        self.cache = SynthesisCacheManager(
            namespace=self.config.cache.namespace,
            root=Path(self.config.cache.directory) if self.config.cache.directory else None,
            enabled=self.config.cache.enabled,
        )
        self.streaming_manager = StreamingManager(self.config.streaming)
        self.exporter = AudioExportManager(self.config.export)
        self.router = EngineRouter(self.config.routing)
        self.realtime_pipeline = RealTimePipeline(
            self.streaming_manager, self.pronunciation, self.emotions
        )
        self.quality_pipeline = QualityPipeline(
            max_chunk_chars=self.config.streaming.max_sentence_chars,
            peak_dbfs=self.config.export.peak_dbfs,
        )
        self._engines: dict[str, BaseVoiceAdapter] = {}
        self._active_model: str | None = None

    # ------------------------------------------------------------------ models
    def load_model(
        self,
        model_id: str | None = None,
        device: str | None = None,
        model_config: dict[str, Any] | None = None,
        eager: bool = False,
    ) -> BaseVoiceAdapter:
        """Register a model as the active engine (weights load lazily).

        Args:
            model_id: Adapter id; defaults to ``engine.default_model``.
            device: Overrides the configured device for this model.
            model_config: Overrides the configured per-model adapter config.
            eager: Load weights now instead of on first synthesis.
        """
        model_id = model_id or self.config.engine.default_model
        adapter = self._engines.get(model_id)
        if adapter is None:
            # Reuse an already-loaded adapter from the process-global cache when one
            # exists (avoids reloading weights across VoiceEngine instances); falls
            # back to constructing a fresh adapter otherwise (Phase C17).
            adapter = get_or_create_adapter(
                model_id,
                device=device or self.config.engine.device,
                config=(
                    model_config
                    if model_config is not None
                    else self.config.engine.models.get(model_id, {})
                ),
            )
            self._engines[model_id] = adapter
        if eager:
            adapter.load()
        self._active_model = model_id
        return adapter

    def switch_model(self, model_id: str) -> BaseVoiceAdapter:
        """Make ``model_id`` the active engine (alias of :meth:`load_model`)."""
        return self.load_model(model_id)

    def unload_model(self, model_id: str | None = None) -> None:
        """Release one model's memory (active model if unspecified)."""
        model_id = model_id or self._active_model
        if model_id is None:
            return
        adapter = self._engines.pop(model_id, None)
        if adapter is not None:
            adapter.unload()
            forget_cached_adapter(adapter)   # unload truly forgets it (Phase C17)
        if self._active_model == model_id:
            self._active_model = None

    def unload_all(self) -> None:
        for model_id in list(self._engines):
            self.unload_model(model_id)

    @property
    def active_model(self) -> str | None:
        return self._active_model

    def loaded_models(self) -> list[str]:
        return sorted(self._engines)

    @staticmethod
    def available_models() -> list[str]:
        """Adapter ids whose optional dependencies are installed."""
        return available_adapter_ids()

    def model_for_use_case(
        self,
        use_case: str,
        language: Language | str | None = None,
        require_cloning: bool = False,
    ) -> str:
        """Resolve a configured routing chain (e.g. ``realtime``/``quality``)."""
        return self.router.resolve(
            use_case, language=self._language(language), require_cloning=require_cloning
        )

    # ------------------------------------------------------------------ cloning
    def clone_voice(
        self,
        reference_audio: Path | str,
        name: str,
        model_id: str | None = None,
        language_hint: Language | str | None = None,
        consent: str | None = None,
        save: bool = True,
    ) -> VoiceProfile:
        """Create a voice profile from reference audio.

        Args:
            reference_audio: Clean 16-bit WAV, ideally ~20 s (A1.5 study).
            name: Human-readable voice name.
            model_id: Cloning engine; defaults to the active model if it can
                clone, else the configured ``cloning`` routing chain.
            language_hint: Primary language of the reference speaker.
            consent: Consent statement (who, when, permitted use). Required
                to save unless the profile store is configured otherwise.
            save: Persist the profile immediately.
        """
        if model_id is None and self._active_model is not None:
            if ADAPTER_CLASSES[self._active_model].CAPABILITIES.zero_shot_cloning:
                model_id = self._active_model
        if model_id is None:
            model_id = self.router.resolve("cloning", require_cloning=True)
        adapter = self.load_model(model_id)
        profile = adapter.create_voice_profile(
            Path(reference_audio),
            display_name=name,
            language_hint=self._language(language_hint),
        )
        if consent:
            profile.metadata[CONSENT_KEY] = consent
        if save:
            profile = self.profiles.save(profile)
        logger.info(
            "Voice cloned",
            extra={"context": {"profile_id": profile.profile_id, "engine": model_id}},
        )
        return profile

    # ------------------------------------------------------------------ profiles
    def save_profile(self, profile: VoiceProfile) -> VoiceProfile:
        return self.profiles.save(profile)

    def load_profile(self, profile_id: str) -> VoiceProfile:
        return self.profiles.load(profile_id)

    def list_profiles(self, engine_id: str | None = None) -> list[VoiceProfile]:
        return self.profiles.list_profiles(engine_id)

    def delete_profile(self, profile_id: str) -> bool:
        return self.profiles.delete(profile_id)

    # ------------------------------------------------------------------ synthesis
    def generate(
        self,
        text: str,
        language: Language | str = Language.ENGLISH,
        voice: VoiceProfile | str | None = None,
        speed: float = 1.0,
        emotion: EmotionSpec | str | None = None,
        model_id: str | None = None,
        output_path: Path | str | None = None,
        seed: int | None = None,
        extra: dict[str, Any] | None = None,
        use_cache: bool = True,
        long_form: bool = False,
    ) -> SynthesisResult:
        """Synthesize speech for ``text`` and return the result.

        Args:
            voice: A profile object or a stored profile id; None uses the
                engine's default voice.
            emotion: Emotion name or :class:`EmotionSpec` (with intensity).
            model_id: Engine for this call; defaults to the active model.
            use_cache: Serve/store this synthesis via the output cache.
            long_form: Route through the quality pipeline (sentence chunking
                + crossfade); use for narration longer than one utterance.
        """
        engine, request = self._prepare(
            text, language, voice, speed, emotion, model_id, output_path, seed, extra
        )
        if use_cache:
            cached = self.cache.get(request, engine.engine_id)
            if cached is not None:
                return cached
        if long_form:
            result = self.quality_pipeline.run(engine, request)
        else:
            result = engine.synthesize(request)
        if use_cache:
            self.cache.put(request, engine.engine_id, result)
        return result

    async def agenerate(self, *args: Any, **kwargs: Any) -> SynthesisResult:
        """Async :meth:`generate` (runs on a worker thread)."""
        return await asyncio.to_thread(self.generate, *args, **kwargs)

    def stream(
        self,
        text: str,
        language: Language | str = Language.ENGLISH,
        voice: VoiceProfile | str | None = None,
        speed: float = 1.0,
        emotion: EmotionSpec | str | None = None,
        model_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[AudioChunk]:
        """Stream PCM chunks (native engine streaming or sentence fallback).

        Stop iterating (or ``close()`` the generator) to barge in.
        """
        engine, request = self._prepare(
            text, language, voice, speed, emotion, model_id, None, None, extra
        )
        return self.streaming_manager.stream(engine, request)

    async def astream(
        self,
        text: str,
        language: Language | str = Language.ENGLISH,
        voice: VoiceProfile | str | None = None,
        speed: float = 1.0,
        emotion: EmotionSpec | str | None = None,
        model_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[AudioChunk]:
        """Async :meth:`stream` for Pipecat-style pipelines."""
        engine, request = self._prepare(
            text, language, voice, speed, emotion, model_id, None, None, extra
        )
        async for chunk in self.streaming_manager.astream(engine, request):
            yield chunk

    # ------------------------------------------------------------------ export
    def export(
        self,
        source: SynthesisResult | Path | str,
        output_path: Path | str,
        audio_format: AudioFormat | str | None = None,
        sample_rate: int | None = None,
        peak_dbfs: float | None = None,
    ) -> Path:
        """Export synthesized audio to a delivery format (WAV/MP3/OGG/FLAC)."""
        source_path = source.audio_path if isinstance(source, SynthesisResult) else source
        return self.exporter.export(
            source_path, output_path, audio_format, sample_rate, peak_dbfs
        )

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _language(language: Language | str | None) -> Language | None:
        if language is None or isinstance(language, Language):
            return language
        return Language.from_code(language)

    def _resolve_voice(self, voice: VoiceProfile | str | None) -> VoiceProfile | None:
        if isinstance(voice, str):
            return self.profiles.load(voice)
        return voice

    def _prepare(
        self,
        text: str,
        language: Language | str,
        voice: VoiceProfile | str | None,
        speed: float,
        emotion: EmotionSpec | str | None,
        model_id: str | None,
        output_path: Path | str | None,
        seed: int | None,
        extra: dict[str, Any] | None,
    ) -> tuple[BaseVoiceAdapter, SynthesisRequest]:
        """Resolve the engine and build the fully front-ended request."""
        if not text or not text.strip():
            raise ModelError("Cannot synthesize empty text")
        engine = (
            self.load_model(model_id)
            if model_id or self._active_model is None
            else self._engines[self._active_model]
        )
        lang = self._language(language) or Language.ENGLISH
        profile = self._resolve_voice(voice)
        if profile is not None and profile.engine_id != engine.engine_id:
            raise ModelError(
                f"Voice profile {profile.profile_id!r} belongs to engine "
                f"{profile.engine_id!r}, not {engine.engine_id!r}; re-clone or switch models",
                profile_id=profile.profile_id,
            )
        spec = resolve_emotion(emotion)
        request = SynthesisRequest(
            text=text,
            language=lang,
            voice=profile,
            speed=speed,
            emotion=spec.emotion.value if spec else None,
            seed=seed,
            output_path=Path(output_path) if output_path else None,
            extra=dict(extra) if extra else {},
        )
        request = replace(request, text=self.pronunciation.apply(request.text, lang))
        request = self.emotions.render(request, engine, spec)
        return engine, request

    # ------------------------------------------------------------------ lifecycle
    def __enter__(self) -> "VoiceEngine":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.unload_all()
