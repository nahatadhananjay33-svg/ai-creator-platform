"""CosyVoice 2 adapter (Alibaba FunAudioLLM).

0.5B LLM-based TTS with a chunk-aware flow-matching decoder designed for
bidirectional streaming: ~150 ms first-packet latency with zero-shot cloning.

Key research facts (see voice_engine/research/cosyvoice2.md):
- Apache-2.0 code and weights -> commercial-friendly.
- The strongest *native streaming* architecture among open cloning models;
  the reference design for our real-time tier.
- Languages: ZH (best), EN, JA, KO + Chinese dialects. No Hindi/Bengali;
  fine-tuning recipes exist (data required).
- Installation is the most complex of the candidates (pinned deps,
  matcha-tts, optional ttsfrd resources).
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class CosyVoice2Adapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="cosyvoice2",
        display_name="CosyVoice 2 (Alibaba)",
        family="tts",
        version="2.0-0.5B (2024-12, line continued by CosyVoice 3)",
        repo_url="https://github.com/FunAudioLLM/CosyVoice",
        weights_source="FunAudioLLM/CosyVoice2-0.5B (Hugging Face / ModelScope)",
        license=LicenseInfo(
            code_license="Apache-2.0",
            weights_license="Apache-2.0",
            commercial_use=True,
        ),
        hardware=HardwareRequirements(
            min_vram_gb=4, recommended_vram_gb=8, min_ram_gb=16,
            cpu_realtime_capable=False, disk_size_gb=3.0,
            notes="~150 ms first-packet streaming latency on RTX-class GPUs.",
        ),
        parameters_millions=500,
        languages=("zh", "en", "ja", "ko"),
        tags=("zero-shot", "streaming", "commercial-ok", "low-latency", "finetunable"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=True,
        streaming=StreamingSupport.EXCELLENT,
        emotion_control=True,  # instruct-mode style control
        languages=(Language.ENGLISH,),
        min_reference_audio_s=3.0,
        cpu_realtime=False,
        notes="No Hindi/Bengali out of the box; Indian-language support would "
        "require fine-tuning with in-house data (recipes provided upstream).",
    )
    IMPORT_PACKAGES = ("cosyvoice",)
    PIP_PACKAGES = ("cosyvoice (install from source; see voice_engine/docs/INSTALLATION.md)",)

    def _load_impl(self) -> None:
        # Verified against CosyVoice2 README API; re-verify on install.
        from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore[import-not-found]

        self._model = CosyVoice2(
            self.config.get("model_dir", "pretrained_models/CosyVoice2-0.5B"),
            load_jit=False,
            load_trt=False,
            fp16=self.device.value == "cuda",
        )

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("CosyVoice 2 requires a voice profile with reference audio")
        import torchaudio  # type: ignore[import-not-found]

        from cosyvoice.utils.file_utils import load_wav  # type: ignore[import-not-found]

        prompt = load_wav(str(request.voice.reference_audio), 16000)
        ref_text = request.voice.metadata.get("reference_text", "")
        chunks = [
            out["tts_speech"]
            for out in self._model.inference_zero_shot(
                request.text, ref_text, prompt, stream=False, speed=request.speed
            )
        ]
        import torch  # type: ignore[import-not-found]

        torchaudio.save(str(output_path), torch.cat(chunks, dim=1), self._model.sample_rate)
