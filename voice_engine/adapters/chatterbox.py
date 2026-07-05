"""Chatterbox adapter (Resemble AI).

0.5B-parameter Llama-backbone TTS with zero-shot cloning and a unique
emotion-exaggeration control; outputs carry Resemble's PerTh watermark.

Key research facts (see voice_engine/research/chatterbox.md):
- MIT license (code + weights) -> commercial-friendly.
- Chatterbox Multilingual (2025) extends to 23 languages including Hindi.
- ~6.5 GB VRAM in fp16; no official streaming (community forks add chunked
  token streaming) -> LIMITED officially.
- Strong blind-test results vs commercial systems for English.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class ChatterboxAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="chatterbox",
        display_name="Chatterbox (Resemble AI)",
        family="tts",
        version="Multilingual (2025)",
        repo_url="https://github.com/resemble-ai/chatterbox",
        weights_source="ResembleAI/chatterbox (Hugging Face)",
        license=LicenseInfo(
            code_license="MIT",
            weights_license="MIT",
            commercial_use=True,
            notes="Outputs watermarked (PerTh); watermark is imperceptible but detectable.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=6, recommended_vram_gb=8, min_ram_gb=16,
            cpu_realtime_capable=False, disk_size_gb=4.0,
            notes="fp16 GPU strongly recommended; CPU inference is far from real time.",
        ),
        parameters_millions=500,
        languages=("en", "hi", "ar", "zh", "fr", "de", "es", "it", "ja", "ko",
                   "pt", "ru", "tr", "nl", "pl", "sv", "da", "fi", "no", "el",
                   "he", "ms", "sw"),
        tags=("zero-shot", "emotion-control", "commercial-ok", "hindi-native", "watermarked"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=False,
        streaming=StreamingSupport.LIMITED,
        emotion_control=True,
        languages=(Language.ENGLISH, Language.HINDI, Language.HINGLISH),
        min_reference_audio_s=7.0,
        cpu_realtime=False,
        notes="Hindi via multilingual checkpoint; Hinglish via romanized text (verify "
        "code-switch quality in listening tests). No Bengali as of 2025 releases.",
    )
    IMPORT_PACKAGES = ("chatterbox",)
    PIP_PACKAGES = ("chatterbox-tts",)

    def _load_impl(self) -> None:
        # Verified against chatterbox-tts >=0.1 API; re-verify pinned version on install.
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore[import-not-found]

        self._model = ChatterboxMultilingualTTS.from_pretrained(device=self.device.value)

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("Chatterbox requires a voice profile with reference audio")
        import soundfile as sf  # type: ignore[import-not-found]

        lang = "hi" if request.language in (Language.HINDI, Language.HINGLISH) else "en"
        exaggeration = 0.7 if request.emotion in ("excited", "happy") else 0.5
        wav = self._model.generate(
            request.text,
            language_id=lang,
            audio_prompt_path=str(request.voice.reference_audio),
            exaggeration=exaggeration,
        )
        # PCM_16 (platform interchange format); torchaudio.save would emit float32
        sf.write(str(output_path), wav.squeeze(0).cpu().numpy(), self._model.sr, subtype="PCM_16")
