"""Kokoro adapter (hexgrad).

82M-parameter StyleTTS2-derived model: exceptional quality-per-parameter,
CPU real-time, Apache-2.0. No voice cloning — curated voice packs — but it
ships Hindi voices, which makes it a serious real-time Voice-AI candidate.

Key research facts (see voice_engine/research/emerging_models.md):
- Apache-2.0 code + weights -> commercial-friendly.
- Voices: EN (US/GB) + HI (hf_alpha/hf_beta/hm_omega/hm_psi), plus JA/ZH/ES/FR/IT/PT.
- CPU real-time (RTF < 0.5 on laptop cores; far faster on GPU) -> chunked
  streaming works well; widely used in real-time agent stacks.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class KokoroAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="kokoro",
        display_name="Kokoro-82M",
        family="tts",
        version="v1.0 (2025)",
        repo_url="https://github.com/hexgrad/kokoro",
        weights_source="hexgrad/Kokoro-82M (Hugging Face)",
        license=LicenseInfo(
            code_license="Apache-2.0",
            weights_license="Apache-2.0",
            commercial_use=True,
        ),
        hardware=HardwareRequirements(
            min_vram_gb=None, recommended_vram_gb=2, min_ram_gb=4,
            cpu_realtime_capable=True, disk_size_gb=0.4,
            notes="Runs real-time on CPU; trivial on any GPU.",
        ),
        parameters_millions=82,
        languages=("en", "hi", "ja", "zh", "es", "fr", "it", "pt"),
        tags=("cpu-realtime", "commercial-ok", "no-cloning", "hindi-native", "lightweight"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=False,
        fine_tuning=False,
        streaming=StreamingSupport.GOOD,
        emotion_control=False,
        languages=(Language.ENGLISH, Language.HINDI),
        min_reference_audio_s=None,
        cpu_realtime=True,
        notes="Fixed voice packs incl. Hindi female/male. Sentence-chunked streaming "
        "achieves low perceived latency because RTF << 1 even on CPU.",
    )
    IMPORT_PACKAGES = ("kokoro",)
    PIP_PACKAGES = ("kokoro",)

    #: kokoro lang codes per platform language ('a' = American English, 'h' = Hindi).
    _LANG_CODES = {Language.ENGLISH: "a", Language.HINDI: "h"}
    _DEFAULT_VOICES = {Language.ENGLISH: "af_heart", Language.HINDI: "hf_alpha"}

    def _load_impl(self) -> None:
        # Verified against kokoro 1.0 API (validated on install, Phase A1.5).
        # Pipelines are created lazily per language; the model itself is shared.
        self._model = {}

    def _pipeline(self, language: Language):  # noqa: ANN202 - KPipeline (optional dep)
        from kokoro import KPipeline  # type: ignore[import-not-found]

        lang_code = self._LANG_CODES[language]
        if lang_code not in self._model:
            self._model[lang_code] = KPipeline(lang_code=lang_code, repo_id="hexgrad/Kokoro-82M")
        return self._model[lang_code]

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        import numpy as np  # type: ignore[import-not-found]
        import soundfile as sf  # type: ignore[import-not-found]

        pipeline = self._pipeline(request.language)
        voice = self.config.get("voice", self._DEFAULT_VOICES[request.language])
        segments = [audio for _, _, audio in pipeline(request.text, voice=voice, speed=request.speed)]
        if not segments:
            raise RuntimeError("kokoro produced no audio segments")
        audio = np.concatenate(segments)
        # write 16-bit PCM (platform interchange format)
        sf.write(str(output_path), audio, 24000, subtype="PCM_16")
