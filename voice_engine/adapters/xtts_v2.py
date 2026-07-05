"""XTTS v2 adapter (Coqui / Idiap-maintained fork).

GPT-style autoregressive latent model + HiFi-GAN decoder; zero-shot cloning
from ~6 s of reference audio; 17 languages including Hindi.

Key research facts (see voice_engine/research/xtts_v2.md):
- Code MPL-2.0 (idiap/coqui-ai-TTS fork), weights under the Coqui Public
  Model License: NON-COMMERCIAL. This alone disqualifies XTTS v2 for our
  production deployment; it remains a strong quality/latency baseline.
- ~467M params (~1.9 GB). Native chunked streaming (<300 ms first chunk on
  modern GPUs) -> GOOD/EXCELLENT streaming among open models.
- Coqui (company) shut down in 2024; the Idiap fork is the maintained line.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class XTTSv2Adapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="xtts-v2",
        display_name="XTTS v2 (Coqui)",
        family="tts",
        version="2.0.3 (fork-maintained)",
        repo_url="https://github.com/idiap/coqui-ai-TTS",
        weights_source="coqui/XTTS-v2 (Hugging Face)",
        license=LicenseInfo(
            code_license="MPL-2.0",
            weights_license="Coqui Public Model License (non-commercial)",
            commercial_use=False,
            notes="CPML prohibits commercial use of the released weights. "
            "Benchmark baseline only for this platform.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=4, recommended_vram_gb=8, min_ram_gb=8,
            cpu_realtime_capable=False, disk_size_gb=2.0,
            notes="Streaming first-chunk <300 ms on RTX-class GPUs.",
        ),
        parameters_millions=467,
        languages=("en", "hi", "es", "fr", "de", "it", "pt", "pl", "tr", "ru",
                   "nl", "cs", "ar", "zh", "ja", "hu", "ko"),
        tags=("zero-shot", "autoregressive", "streaming", "multilingual", "hindi-native"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=True,
        streaming=StreamingSupport.GOOD,
        emotion_control=False,
        languages=(Language.ENGLISH, Language.HINDI, Language.HINGLISH),
        min_reference_audio_s=6.0,
        cpu_realtime=False,
        notes="Hindi is natively supported (Devanagari input). Hinglish works by "
        "passing romanized text with language='hi' or 'en' — quality varies; "
        "no Bengali support.",
    )
    IMPORT_PACKAGES = ("TTS",)
    PIP_PACKAGES = ("coqui-tts",)

    def _load_impl(self) -> None:
        # Verified against coqui-tts >=0.24 API; re-verify pinned version on install.
        from TTS.api import TTS  # type: ignore[import-not-found]

        self._model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device.value)

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("XTTS v2 requires a voice profile with reference audio")
        # Hinglish: romanized text is synthesized with the Hindi decoder path.
        language = "hi" if request.language in (Language.HINDI, Language.HINGLISH) else "en"
        self._model.tts_to_file(
            text=request.text,
            speaker_wav=str(request.voice.reference_audio),
            language=language,
            file_path=str(output_path),
            speed=request.speed,
        )
