"""F5-TTS adapter.

F5-TTS (SWivid): flow-matching Diffusion Transformer (DiT) with ConvNeXt v2
text conditioning; non-autoregressive, zero-shot cloning from a short
reference clip + its transcript.

Key research facts (see voice_engine/research/f5_tts.md):
- Code MIT; default checkpoints trained on Emilia are CC-BY-NC-4.0 ->
  NOT commercially usable without retraining/relicensing. IndicF5
  (AI4Bharat) covers 11 Indian languages under its own terms.
- ~336M parameters, ~1.35 GB weights. GPU RTF ~0.15-0.3 (RTX 3060+),
  CPU far from real time.
- No native streaming; chunked inference only (LIMITED).
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class F5TTSAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="f5-tts",
        display_name="F5-TTS",
        family="tts",
        version="v1 (2024-10, maintained through 2025)",
        repo_url="https://github.com/SWivid/F5-TTS",
        weights_source="SWivid/F5-TTS_v1 (Hugging Face)",
        license=LicenseInfo(
            code_license="MIT",
            weights_license="CC-BY-NC-4.0 (Emilia-trained base)",
            commercial_use=False,
            notes="Commercial use requires retraining on permissive data or a licensed "
            "finetune. IndicF5 (AI4Bharat) adds 11 Indian languages; check its weight license.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=4, recommended_vram_gb=8, min_ram_gb=8,
            cpu_realtime_capable=False, disk_size_gb=1.5,
            notes="RTF ~0.15-0.3 on RTX 3060/4070; CPU RTF >3 (offline only).",
        ),
        parameters_millions=336,
        languages=("en", "zh", "hi*", "bn*"),  # * via IndicF5 finetune
        tags=("zero-shot", "flow-matching", "high-quality", "finetunable"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=True,
        streaming=StreamingSupport.LIMITED,
        emotion_control=False,  # inherits emotion from reference audio only
        languages=(Language.ENGLISH, Language.HINDI, Language.HINGLISH, Language.BENGALI),
        min_reference_audio_s=5.0,
        cpu_realtime=False,
        notes="HI/BN require the IndicF5 finetune; base model is EN/ZH. "
        "Hinglish works via romanized text with the Indic finetune (verify in listening tests).",
    )
    IMPORT_PACKAGES = ("f5_tts",)
    PIP_PACKAGES = ("f5-tts",)

    def _load_impl(self) -> None:
        # Verified against F5-TTS >=1.0 API docs; re-verify pinned version on install.
        from f5_tts.api import F5TTS  # type: ignore[import-not-found]

        self._model = F5TTS(
            model=self.config.get("model_name", "F5TTS_v1_Base"),
            device=self.device.value,
        )

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("F5-TTS requires a voice profile with reference audio")
        self._model.infer(
            ref_file=str(request.voice.reference_audio),
            ref_text=request.voice.metadata.get("reference_text", ""),
            gen_text=request.text,
            file_wave=str(output_path),
            speed=request.speed,
            seed=request.seed if request.seed is not None else -1,
        )
