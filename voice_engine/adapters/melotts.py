"""MeloTTS adapter (MyShell).

Lightweight VITS-family multi-lingual TTS. No voice cloning — fixed library
voices — but genuinely CPU real-time, which makes it a latency/efficiency
baseline and the base synthesizer inside OpenVoice V2.

Key research facts (see voice_engine/research/medium_priority_models.md):
- MIT code + weights -> commercial-friendly.
- Languages: EN (US/UK/AU/**Indian accent**), ZH, JA, KO, ES, FR. The EN-India
  accent matters for our English real-estate agent persona.
- No Hindi/Bengali text support; no cloning; no emotion control.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class MeloTTSAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="melotts",
        display_name="MeloTTS",
        family="tts",
        version="2024 releases",
        repo_url="https://github.com/myshell-ai/MeloTTS",
        weights_source="myshell-ai/MeloTTS-* (Hugging Face)",
        license=LicenseInfo(
            code_license="MIT",
            weights_license="MIT",
            commercial_use=True,
        ),
        hardware=HardwareRequirements(
            min_vram_gb=None, recommended_vram_gb=2, min_ram_gb=4,
            cpu_realtime_capable=True, disk_size_gb=0.5,
            notes="CPU real-time even on laptop cores.",
        ),
        parameters_millions=52,
        languages=("en", "en-in", "zh", "ja", "ko", "es", "fr"),
        tags=("cpu-realtime", "commercial-ok", "no-cloning", "lightweight"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=False,
        fine_tuning=True,
        streaming=StreamingSupport.LIMITED,
        emotion_control=False,
        languages=(Language.ENGLISH,),
        min_reference_audio_s=None,
        cpu_realtime=True,
        notes="Fixed voices only. EN-India accent available. Sentence-chunked "
        "pseudo-streaming is viable because synthesis is faster than real time on CPU.",
    )
    IMPORT_PACKAGES = ("melo",)
    PIP_PACKAGES = ("git+https://github.com/myshell-ai/MeloTTS.git",)

    def _load_impl(self) -> None:
        # Verified against MeloTTS README API; re-verify on install.
        from melo.api import TTS as MeloTTS  # type: ignore[import-not-found]

        self._model = MeloTTS(
            language=self.config.get("melo_language", "EN"), device=self.device.value
        )

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        # spk2id is a melo HParams object (dict-like: keys()/[] but no .get)
        speaker_ids = self._model.hps.data.spk2id
        keys = list(speaker_ids.keys())
        speaker_key = self.config.get("speaker", "EN-India")
        if speaker_key not in keys:
            speaker_key = keys[0]
        self._model.tts_to_file(
            request.text, speaker_ids[speaker_key], str(output_path), speed=request.speed
        )
