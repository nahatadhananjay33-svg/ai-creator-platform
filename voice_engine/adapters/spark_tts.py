"""Spark-TTS adapter (SparkAudio).

0.5B Qwen2.5-backbone LLM TTS with the single-stream BiCodec tokenizer;
zero-shot cloning plus attribute-controlled voice creation (gender, pitch).

Key research facts (see voice_engine/research/medium_priority_models.md):
- Code Apache-2.0; the released 0.5B weights carry a CC-BY-NC-4.0 marker on
  parts of the release -> treat commercial use as UNCLEAR until verified
  with upstream. Do not deploy commercially without legal confirmation.
- Languages: EN + ZH only. No Hindi/Bengali.
- No native streaming; autoregressive decode is not real-time-tuned.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class SparkTTSAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="spark-tts",
        display_name="Spark-TTS",
        family="tts",
        version="0.5B (2025)",
        repo_url="https://github.com/SparkAudio/Spark-TTS",
        weights_source="SparkAudio/Spark-TTS-0.5B (Hugging Face)",
        license=LicenseInfo(
            code_license="Apache-2.0",
            weights_license="CC-BY-NC-4.0 (verify upstream)",
            commercial_use=False,
            notes="Conflicting license signals between repo and model card; "
            "treat as non-commercial until confirmed.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=4, recommended_vram_gb=8, min_ram_gb=8,
            cpu_realtime_capable=False, disk_size_gb=2.0,
        ),
        parameters_millions=500,
        languages=("en", "zh"),
        tags=("zero-shot", "llm-tts", "voice-creation"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=True,
        streaming=StreamingSupport.LIMITED,
        emotion_control=False,
        languages=(Language.ENGLISH,),
        min_reference_audio_s=5.0,
        cpu_realtime=False,
        notes="EN/ZH only; excluded from Indian-language scoring.",
    )
    IMPORT_PACKAGES = ("sparktts",)
    PIP_PACKAGES = ("spark-tts (install from source; see voice_engine/docs/INSTALLATION.md)",)

    def _load_impl(self) -> None:
        # Verified against Spark-TTS README CLI/API; re-verify on install.
        from sparktts.models.audio_tokenizer import BiCodecTokenizer  # noqa: F401
        from sparktts.cli.SparkTTS import SparkTTS  # type: ignore[import-not-found]

        self._model = SparkTTS(
            self.config.get("model_dir", "pretrained_models/Spark-TTS-0.5B"),
            device=self.device.value,
        )

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("Spark-TTS requires a voice profile with reference audio")
        import soundfile as sf  # type: ignore[import-not-found]

        wav = self._model.inference(
            request.text,
            prompt_speech_path=str(request.voice.reference_audio),
            prompt_text=request.voice.metadata.get("reference_text", ""),
        )
        sf.write(str(output_path), wav, 16000)
