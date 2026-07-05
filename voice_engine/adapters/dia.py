"""Dia adapter (Nari Labs).

1.6B-parameter dialogue-native TTS: generates multi-speaker conversations
([S1]/[S2] tags) with non-verbal sounds (laughs, coughs) in one pass.

Key research facts (see voice_engine/research/dia.md):
- Apache-2.0 code and weights -> commercial-friendly.
- English only; voice cloning via audio-prompt continuation (reference audio
  + its transcript prepended to the script).
- ~10 GB VRAM at full precision (~5-6 GB bf16); generation speed varies and
  pacing can drift on long inputs — built for short dialogue clips, not
  narration. No streaming.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class DiaAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="dia",
        display_name="Dia (Nari Labs)",
        family="tts",
        version="1.6B (2025)",
        repo_url="https://github.com/nari-labs/dia",
        weights_source="nari-labs/Dia-1.6B (Hugging Face)",
        license=LicenseInfo(
            code_license="Apache-2.0",
            weights_license="Apache-2.0",
            commercial_use=True,
        ),
        hardware=HardwareRequirements(
            min_vram_gb=6, recommended_vram_gb=10, min_ram_gb=16,
            cpu_realtime_capable=False, disk_size_gb=6.5,
            notes="bf16 fits ~6 GB; full precision ~10 GB.",
        ),
        parameters_millions=1600,
        languages=("en",),
        tags=("dialogue", "non-verbal", "zero-shot", "commercial-ok"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=False,
        streaming=StreamingSupport.NOT_SUITABLE,
        emotion_control=True,  # via non-verbal tags and audio prompt
        languages=(Language.ENGLISH,),
        min_reference_audio_s=5.0,
        cpu_realtime=False,
        notes="Dialogue clips only; unstable pacing on long-form narration. "
        "English only — not a candidate for HI/BN content.",
    )
    IMPORT_PACKAGES = ("dia",)
    PIP_PACKAGES = ("git+https://github.com/nari-labs/dia.git",)

    def _load_impl(self) -> None:
        # Verified against Dia README API; re-verify on install.
        from dia.model import Dia  # type: ignore[import-not-found]

        self._model = Dia.from_pretrained(
            self.config.get("model_name", "nari-labs/Dia-1.6B"),
            compute_dtype=self.config.get("compute_dtype", "float16"),
        )

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        text = request.text
        if not text.lstrip().startswith("[S1]"):
            text = f"[S1] {text}"
        kwargs: dict[str, object] = {}
        if request.voice is not None and request.voice.reference_audio is not None:
            # Audio-prompt cloning: transcript of the reference must be prepended.
            ref_transcript = request.voice.metadata.get("reference_text", "")
            text = f"{ref_transcript} {text}" if ref_transcript else text
            kwargs["audio_prompt"] = str(request.voice.reference_audio)
        audio = self._model.generate(text, **kwargs)
        self._model.save_audio(str(output_path), audio)
