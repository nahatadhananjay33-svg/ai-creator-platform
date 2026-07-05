"""Indic Parler-TTS adapter (AI4Bharat + Hugging Face).

The most complete open Indian-language TTS: 20 Indic languages + English,
including native Hindi AND Bengali, trained on ~10k hours. Voices are
selected/steered by natural-language description (named recurring speakers),
not cloned from reference audio.

Key research facts (see voice_engine/research/indic_models.md):
- Apache-2.0 code and weights -> commercial-friendly.
- The only candidate with first-class Bengali. Critical for our market.
- No zero-shot audio cloning — speaker identity via description/named
  speakers; consistent enough for a branded agent voice, not for cloning a
  specific person.
- ~880M params (Parler-TTS large architecture); GPU recommended.
"""
from __future__ import annotations

from pathlib import Path

from foundation.constants import Language
from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import EngineCapabilities, StreamingSupport, SynthesisRequest


class IndicParlerAdapter(BaseVoiceAdapter):
    SPEC = ModelSpec(
        model_id="indic-parler",
        display_name="Indic Parler-TTS (AI4Bharat)",
        family="tts",
        version="2024-12 release",
        repo_url="https://github.com/huggingface/parler-tts",
        weights_source="ai4bharat/indic-parler-tts (Hugging Face)",
        license=LicenseInfo(
            code_license="Apache-2.0",
            weights_license="Apache-2.0",
            commercial_use=True,
        ),
        hardware=HardwareRequirements(
            min_vram_gb=6, recommended_vram_gb=8, min_ram_gb=16,
            cpu_realtime_capable=False, disk_size_gb=3.5,
        ),
        parameters_millions=880,
        languages=("hi", "bn", "en", "ta", "te", "kn", "ml", "mr", "gu", "pa",
                   "or", "as", "ur", "ne", "sa", "mai", "doi", "kok", "mni", "sd", "brx"),
        tags=("indic", "hindi-native", "bengali-native", "commercial-ok", "description-voice"),
    )
    CAPABILITIES = EngineCapabilities(
        zero_shot_cloning=False,
        fine_tuning=True,
        streaming=StreamingSupport.LIMITED,
        emotion_control=True,  # via description prompt ("speaks with excitement...")
        languages=(Language.ENGLISH, Language.HINDI, Language.HINGLISH, Language.BENGALI),
        min_reference_audio_s=None,
        cpu_realtime=False,
        notes="Named speakers (e.g. 'Rohit', 'Divya') give reproducible voices; "
        "code-switched Hinglish handled via mixed-script input. Not a cloning model.",
    )
    IMPORT_PACKAGES = ("parler_tts", "transformers")
    PIP_PACKAGES = ("git+https://github.com/huggingface/parler-tts.git", "transformers")

    def _load_impl(self) -> None:
        # Verified against parler-tts README API; re-verify on install.
        import torch  # type: ignore[import-not-found]
        from parler_tts import ParlerTTSForConditionalGeneration  # type: ignore[import-not-found]
        from transformers import AutoTokenizer  # type: ignore[import-not-found]

        model_name = self.config.get("model_name", "ai4bharat/indic-parler-tts")
        model = ParlerTTSForConditionalGeneration.from_pretrained(model_name).to(self.device.value)
        self._model = {
            "model": model,
            "tokenizer": AutoTokenizer.from_pretrained(model_name),
            "desc_tokenizer": AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path),
            "torch": torch,
        }

    def _synthesize_impl(self, request: SynthesisRequest, output_path: Path) -> None:
        import soundfile as sf  # type: ignore[import-not-found]

        bundle = self._model
        description = request.extra.get(
            "voice_description",
            "Rohit speaks in a clear, moderately paced voice with a friendly tone, "
            "very close to the microphone with no background noise.",
        )
        desc_ids = bundle["desc_tokenizer"](description, return_tensors="pt").to(self.device.value)
        prompt_ids = bundle["tokenizer"](request.text, return_tensors="pt").to(self.device.value)
        generation = bundle["model"].generate(
            input_ids=desc_ids.input_ids,
            attention_mask=desc_ids.attention_mask,
            prompt_input_ids=prompt_ids.input_ids,
            prompt_attention_mask=prompt_ids.attention_mask,
        )
        audio = generation.cpu().numpy().squeeze()
        sf.write(str(output_path), audio, bundle["model"].config.sampling_rate)
