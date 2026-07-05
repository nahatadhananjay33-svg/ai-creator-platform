"""StyleTTS 2 adapter.

Style-diffusion + adversarial training; among the fastest high-quality
English models (GPU RTF well below 0.1) with credible human-level MOS on
LJSpeech/LibriTTS benchmarks.

Key research facts (see voice_engine/research/medium_priority_models.md):
- MIT code + weights. Caveat: the standard phonemizer backend (espeak-ng)
  is GPL — use a process boundary or alternative phonemizer for
  proprietary deployments.
- English only in released checkpoints; multilingual requires training.
- Zero-shot style transfer from short references; timbre similarity is
  weaker than LLM-TTS models (style vector, not full speaker latent).
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class StyleTTS2Adapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="styletts2",
        display_name="StyleTTS 2",
        family="tts",
        version="LibriTTS checkpoint (2023, community-maintained)",
        repo_url="https://github.com/yl4579/StyleTTS2",
        weights_source="yl4579/StyleTTS2-LibriTTS (Hugging Face)",
        license=LicenseInfo(
            code_license="MIT",
            weights_license="MIT",
            commercial_use=True,
            notes="espeak-ng phonemizer dependency is GPL-3.0 — isolate behind a "
            "process boundary or swap phonemizer for proprietary builds.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=2, recommended_vram_gb=4, min_ram_gb=8,
            cpu_realtime_capable=True, disk_size_gb=1.0,
            notes="GPU RTF ~0.03-0.1; near-real-time on strong CPUs.",
        ),
        parameters_millions=148,
        languages=("en",),
        tags=("fast", "high-quality", "style-transfer", "commercial-ok"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=True,
        streaming=StreamingSupport.LIMITED,
        emotion_control=False,
        languages=(Language.ENGLISH,),
        min_reference_audio_s=3.0,
        cpu_realtime=True,
        notes="English only. Fast enough for sentence-chunked pseudo-streaming.",
    )
    IMPORT_PACKAGES = ("styletts2",)
    PIP_PACKAGES = ("styletts2",)  # community pip package wrapping upstream

    def _load_impl(self) -> None:
        # Verified against the community styletts2 pip API; re-verify on install.
        from styletts2 import tts  # type: ignore[import-not-found]

        self._model = tts.StyleTTS2()

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        kwargs: dict[str, object] = {"output_wav_file": str(output_path)}
        if request.voice is not None and request.voice.reference_audio is not None:
            kwargs["target_voice_path"] = str(request.voice.reference_audio)
        self._model.inference(request.text, **kwargs)
        # styletts2 writes float WAV; convert to PCM_16 (platform interchange format)
        import soundfile as sf  # type: ignore[import-not-found]

        data, sr = sf.read(str(output_path))
        sf.write(str(output_path), data, sr, subtype="PCM_16")
