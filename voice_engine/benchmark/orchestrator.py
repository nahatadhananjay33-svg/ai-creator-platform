"""Voice benchmark orchestrator."""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkCase, BenchmarkRunner, RunResult
from foundation.constants import Language
from foundation.constants.paths import ensure_dir
from foundation.logging import get_logger
from foundation.shared_utils.text import new_run_id
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.engine import VoiceEngine
from voice_engine.benchmark.config import VoiceBenchmarkConfig
from voice_engine.benchmark.scenarios import StreamingScenarioCase, SynthesisScenarioCase
from voice_engine.datasets import DatasetManager, PromptCategory, PromptItem
from voice_engine.evaluation import SynthesisEvaluator
from voice_engine.interfaces import StreamingTTSEngine, VoiceProfile
from voice_engine.reporting import CsvReporter, JsonReporter, MarkdownReporter

logger = get_logger("voice_engine.benchmark")

#: Streaming scenario uses conversational prompts only (real-time use case).
_STREAMING_CATEGORIES = (PromptCategory.CONVERSATION, PromptCategory.CODE_SWITCHING)


class VoiceBenchmark:
    """Builds and executes a full voice-model benchmark run."""

    def __init__(
        self,
        config: VoiceBenchmarkConfig,
        dataset_manager: DatasetManager | None = None,
        evaluator: SynthesisEvaluator | None = None,
        voice_engine: VoiceEngine | None = None,
    ) -> None:
        self.config = config
        self.dataset_manager = dataset_manager or DatasetManager()
        self.evaluator = evaluator or SynthesisEvaluator()
        # The benchmark is a consumer of the production Voice Engine: it
        # measures the exact adapters (and configs) production serves with.
        self.voice_engine = voice_engine or VoiceEngine()

    # ------------------------------------------------------------------ build
    def _select_prompts(self, language: Language) -> list[PromptItem]:
        dataset = self.dataset_manager.load(language)
        items = list(dataset.items)
        if self.config.categories:
            wanted = {PromptCategory(c) for c in self.config.categories}
            items = [item for item in items if item.category in wanted]
        cap = self.config.max_items_per_language
        if cap and len(items) > cap:
            # Deterministic spread across categories: keep first item per
            # category in dataset order until the cap is reached.
            by_category: dict[str, list[PromptItem]] = {}
            for item in items:
                by_category.setdefault(item.category.value, []).append(item)
            capped: list[PromptItem] = []
            while len(capped) < cap and any(by_category.values()):
                for bucket in by_category.values():
                    if bucket and len(capped) < cap:
                        capped.append(bucket.pop(0))
            items = capped
        return items

    def _voice_for(self, adapter: BaseVoiceAdapter) -> VoiceProfile | None:
        ref = self.config.reference_audio
        if ref is None or not adapter.capabilities.zero_shot_cloning:
            return None
        profile = adapter.create_voice_profile(Path(ref), display_name="benchmark-reference")
        if self.config.reference_text:
            profile.metadata["reference_text"] = self.config.reference_text
        return profile

    def build_cases(self, run_dir: Path) -> list[BenchmarkCase]:
        cases: list[BenchmarkCase] = []
        audio_dir = ensure_dir(run_dir / "audio")
        for adapter_id in self.config.adapters:
            adapter = self.voice_engine.load_model(adapter_id, device=self.config.device)
            voice: VoiceProfile | None = None
            if adapter.is_available():
                try:
                    voice = self._voice_for(adapter)
                except Exception as exc:  # noqa: BLE001 - reference problems shouldn't kill the run
                    logger.warning(
                        "Voice profile creation failed; running without cloning",
                        extra={"context": {"adapter": adapter_id, "error": str(exc)}},
                    )
            for language in self.config.resolved_languages():
                prompts = self._select_prompts(language)
                for prompt in prompts:
                    for rep in range(self.config.repetitions):
                        cases.append(
                            SynthesisScenarioCase(
                                adapter, prompt, self.evaluator, audio_dir, voice, repetition=rep
                            )
                        )
                if self.config.include_streaming_scenario and isinstance(adapter, StreamingTTSEngine):
                    for prompt in prompts:
                        if prompt.category in _STREAMING_CATEGORIES:
                            cases.append(StreamingScenarioCase(adapter, prompt, audio_dir, voice))
        return cases

    # ------------------------------------------------------------------ run
    def run(self) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("voice-bench")
        run_dir = ensure_dir(self.config.resolved_output_dir() / run_id)
        cases = self.build_cases(run_dir)
        logger.info(
            "Voice benchmark starting",
            extra={"context": {"run_id": run_id, "cases": len(cases),
                               "adapters": ",".join(self.config.adapters)}},
        )
        runner = BenchmarkRunner(
            title="Voice cloning model benchmark",
            config=self.config.to_dict(),
            monitor_resources=self.config.monitor_resources,
        )
        run = runner.run(cases, run_id=run_id)

        reports: dict[str, Path] = {
            "csv": CsvReporter().write(run, run_dir),
            "json": JsonReporter().write(run, run_dir),
            "markdown": MarkdownReporter().write(run, run_dir),
        }
        logger.info(
            "Voice benchmark finished",
            extra={"context": {"run_id": run_id, "report": str(reports["markdown"])}},
        )
        return run, reports
