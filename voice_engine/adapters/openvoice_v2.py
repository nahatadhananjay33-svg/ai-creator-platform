"""OpenVoice V2 adapter (MyShell).

Two-stage pipeline: a base TTS (MeloTTS) generates speech, then a tone-color
converter transfers the target speaker's timbre onto it.

Key research facts (see voice_engine/research/openvoice_v2.md):
- MIT license for BOTH code and V2 weights -> fully commercial-friendly.
- Cloning = timbre transfer; prosody/accent come from the base speaker, so
  accent preservation of the cloned speaker is weak by design.
- Languages bounded by MeloTTS base: EN/ES/FR/ZH/JA/KO. No Hindi/Bengali.
- Light: runs on ~2 GB VRAM, CPU possible (slower than real time overall).
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class OpenVoiceV2Adapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="openvoice-v2",
        display_name="OpenVoice V2",
        family="tts",
        version="V2 (2024-04)",
        repo_url="https://github.com/myshell-ai/OpenVoice",
        weights_source="myshell-ai/OpenVoiceV2 (Hugging Face)",
        license=LicenseInfo(
            code_license="MIT",
            weights_license="MIT",
            commercial_use=True,
            notes="One of the few fully MIT voice-cloning stacks.",
        ),
        hardware=HardwareRequirements(
            min_vram_gb=2, recommended_vram_gb=4, min_ram_gb=8,
            cpu_realtime_capable=False, disk_size_gb=1.0,
            notes="Tone converter is light; MeloTTS base is CPU real-time, "
            "converter adds latency.",
        ),
        parameters_millions=None,  # composite pipeline
        languages=("en", "es", "fr", "zh", "ja", "ko"),
        tags=("zero-shot", "tone-conversion", "commercial-ok", "lightweight"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=True,
        fine_tuning=False,
        streaming=StreamingSupport.LIMITED,
        emotion_control=False,
        languages=(Language.ENGLISH,),
        min_reference_audio_s=10.0,
        cpu_realtime=False,
        notes="No Hindi/Bengali/Hinglish path. Cloned timbre only; source prosody "
        "comes from the MeloTTS base speaker.",
    )
    IMPORT_PACKAGES = ("openvoice", "melo")
    PIP_PACKAGES = ("git+https://github.com/myshell-ai/OpenVoice.git", "git+https://github.com/myshell-ai/MeloTTS.git")

    def _load_impl(self) -> None:
        # Verified against OpenVoice V2 README pipeline; re-verify on install.
        from melo.api import TTS as MeloTTS  # type: ignore[import-not-found]
        from openvoice import se_extractor  # type: ignore[import-not-found]
        from openvoice.api import ToneColorConverter  # type: ignore[import-not-found]

        ckpt_dir = Path(self.config.get("converter_checkpoint_dir", "checkpoints_v2/converter"))
        converter = ToneColorConverter(str(ckpt_dir / "config.json"), device=self.device.value)
        converter.load_ckpt(str(ckpt_dir / "checkpoint.pth"))
        self._model = {
            "melo": MeloTTS(language="EN", device=self.device.value),
            "converter": converter,
            "se_extractor": se_extractor,
        }

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        if request.voice is None or request.voice.reference_audio is None:
            raise ValueError("OpenVoice V2 requires a voice profile with reference audio")
        melo = self._model["melo"]
        converter = self._model["converter"]
        se_extractor = self._model["se_extractor"]

        tmp_base = output_path.with_suffix(".base.wav")
        speaker_ids = melo.hps.data.spk2id
        melo.tts_to_file(
            request.text, list(speaker_ids.values())[0], str(tmp_base), speed=request.speed
        )
        target_se, _ = se_extractor.get_se(
            str(request.voice.reference_audio), converter, vad=True
        )
        source_se, _ = se_extractor.get_se(str(tmp_base), converter, vad=True)
        converter.convert(
            audio_src_path=str(tmp_base),
            src_se=source_se,
            tgt_se=target_se,
            output_path=str(output_path),
        )
        tmp_base.unlink(missing_ok=True)
