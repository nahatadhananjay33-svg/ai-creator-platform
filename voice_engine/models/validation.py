"""Model validation framework.

Verifies, for an installed adapter (run *inside its venv*): model loads,
inference works, reference audio accepted, output audio produced, no
runtime exceptions — and measures init time, first vs subsequent inference,
and memory. Results serialize to JSON for the installation/benchmark reports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.benchmarking import ResourceMonitor
from foundation.constants import Language
from foundation.logging import get_logger
from foundation.shared_utils import Stopwatch
from foundation.shared_utils.timing import utc_now_iso
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.interfaces import SynthesisRequest, VoiceProfile

logger = get_logger("voice_engine.models.validation")

_SMOKE_TEXT = {
    Language.ENGLISH: "The three bedroom apartment has a carpet area of fourteen hundred square feet.",
    Language.HINDI: "यह फ्लैट सातवीं मंज़िल पर है और इसमें दो पार्किंग शामिल हैं।",
    Language.HINGLISH: "Sir, yeh flat seventh floor par hai aur do parking included hai.",
    Language.BENGALI: "এই ফ্ল্যাটটি সাত তলায় এবং দুটি পার্কিং রয়েছে।",
}


@dataclass
class ModelValidationResult:
    model_id: str
    validated_at: str = field(default_factory=utc_now_iso)
    dependencies_ok: bool = False
    loads: bool = False
    inference_ok: bool = False
    reference_accepted: bool | None = None  # None = engine has no cloning
    output_generated: bool = False
    init_time_s: float | None = None
    first_inference_s: float | None = None
    subsequent_inference_s: float | None = None
    first_audio_duration_s: float | None = None
    peak_rss_mb: float | None = None
    languages_ok: list[str] = field(default_factory=list)
    languages_failed: dict[str, str] = field(default_factory=dict)
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.dependencies_ok and self.loads and self.inference_ok and self.output_generated

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "valid": self.valid}


class ModelValidator:
    """Runs the standard validation battery against one adapter instance."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate(
        self,
        adapter: BaseVoiceAdapter,
        reference_audio: Path | None = None,
        languages: tuple[Language, ...] | None = None,
        reference_text: str = "",
    ) -> ModelValidationResult:
        result = ModelValidationResult(model_id=adapter.engine_id)

        result.dependencies_ok = adapter.is_available()
        if not result.dependencies_ok:
            result.error = f"dependencies missing: {adapter.PIP_PACKAGES}"
            return result

        monitor = ResourceMonitor(interval_s=0.5).start()
        try:
            # --- load ---
            try:
                with Stopwatch() as sw:
                    adapter.load()
                result.init_time_s = round(sw.elapsed_s, 2)
                result.loads = True
            except Exception as exc:  # noqa: BLE001 - must capture any model failure
                result.error = f"load failed: {type(exc).__name__}: {str(exc)[:500]}"
                return result

            # --- voice profile / reference acceptance ---
            voice: VoiceProfile | None = None
            if adapter.capabilities.zero_shot_cloning and reference_audio is not None:
                try:
                    voice = adapter.create_voice_profile(reference_audio, "validation-ref")
                    if reference_text:
                        voice.metadata["reference_text"] = reference_text
                    result.reference_accepted = True
                except Exception as exc:  # noqa: BLE001
                    result.reference_accepted = False
                    logger.warning("Reference rejected",
                                   extra={"context": {"model": adapter.engine_id,
                                                      "error": str(exc)[:200]}})

            # --- inference per supported language ---
            langs = languages or adapter.capabilities.languages
            first = True
            for language in langs:
                if language not in adapter.capabilities.languages:
                    continue
                out_path = self.output_dir / f"{adapter.engine_id}-{language.value}-smoke.wav"
                request = SynthesisRequest(
                    text=_SMOKE_TEXT[language], language=language,
                    voice=voice, output_path=out_path,
                )
                try:
                    with Stopwatch() as sw:
                        synthesis = adapter.synthesize(request)
                    if first:
                        result.first_inference_s = round(sw.elapsed_s, 2)
                        result.first_audio_duration_s = round(synthesis.audio_duration_s, 2)
                        first = False
                    else:
                        result.subsequent_inference_s = round(sw.elapsed_s, 2)
                    if synthesis.audio_path.exists() and synthesis.audio_duration_s > 0.1:
                        result.output_generated = True
                        result.inference_ok = True
                        result.languages_ok.append(language.value)
                    else:
                        result.languages_failed[language.value] = "empty/near-empty audio"
                except Exception as exc:  # noqa: BLE001
                    result.languages_failed[language.value] = (
                        f"{type(exc).__name__}: {str(exc)[:300]}"
                    )
        finally:
            monitor.stop()
            if monitor.peak is not None:
                result.peak_rss_mb = round(monitor.peak.rss_mb, 1)
            try:
                adapter.unload()
            except Exception:  # noqa: BLE001
                pass
        if not result.inference_ok and result.error is None and result.languages_failed:
            result.error = "; ".join(f"{k}: {v}" for k, v in result.languages_failed.items())[:800]
        return result

    def save(self, result: ModelValidationResult) -> Path:
        path = self.output_dir / f"{result.model_id}-validation.json"
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path
