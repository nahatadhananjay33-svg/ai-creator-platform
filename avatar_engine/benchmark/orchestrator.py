"""Avatar benchmark orchestrator."""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkCase, BenchmarkRunner, RunResult
from foundation.constants.paths import ensure_dir
from foundation.exceptions import BenchmarkError
from foundation.logging import get_logger
from foundation.reporting import CsvReporter, JsonReporter
from foundation.shared_utils.text import new_run_id

from avatar_engine.benchmark.config import AvatarBenchmarkConfig
from avatar_engine.benchmark.scenarios import GenerationScenarioCase
from avatar_engine.datasets import AvatarDatasetManager, ScenarioCategory
from avatar_engine.evaluation import GenerationEvaluator
from avatar_engine.models import create_adapter
from avatar_engine.reporting import AvatarMarkdownReporter
from voice_engine.metrics import (
    AudioValidation,
    validate_wav,
    write_audio_validation_report,
)

logger = get_logger("avatar_engine.benchmark")


class AvatarBenchmark:
    """Builds and executes a full avatar-model benchmark run."""

    def __init__(
        self,
        config: AvatarBenchmarkConfig,
        dataset_manager: AvatarDatasetManager | None = None,
        evaluator: GenerationEvaluator | None = None,
    ) -> None:
        self.config = config
        self.dataset_manager = dataset_manager or AvatarDatasetManager(
            assets_dir=Path(config.assets_dir) if config.assets_dir else None
        )
        self.evaluator = evaluator or GenerationEvaluator()
        #: scenario_id -> AudioValidation (populated in _select_scenarios).
        self._audio_validations: dict[str, AudioValidation] = {}

    # ------------------------------------------------------------------ build
    def _select_scenarios(self):  # noqa: ANN202 - list[AvatarScenario]
        dataset = self.dataset_manager.load()
        scenarios = list(dataset.scenarios)
        if self.config.categories:
            wanted = {ScenarioCategory(c) for c in self.config.categories}
            scenarios = [s for s in scenarios if s.category in wanted]
        if not scenarios:
            raise BenchmarkError(
                "No scenarios selected", categories=self.config.categories
            )
        cap = self.config.max_scenarios
        if cap and len(scenarios) > cap:
            scenarios = scenarios[:cap]

        missing = self.dataset_manager.missing_assets(
            type(dataset)(dataset.description, dataset.version, scenarios)
        )
        if missing:
            if not self.config.allow_placeholder_assets:
                raise BenchmarkError(
                    "Missing benchmark assets and placeholders disabled",
                    scenarios=sorted(missing),
                )
            self.dataset_manager.generate_placeholder_assets(
                type(dataset)(dataset.description, dataset.version, scenarios)
            )
            logger.warning(
                "Run uses placeholder assets — metrics are wiring-only, not quotable",
                extra={"context": {"scenarios": sorted(missing)}},
            )

        if self.config.validate_audio:
            self._validate_scenario_audio(scenarios)
        return scenarios

    def _validate_scenario_audio(self, scenarios) -> None:
        """Classify each scenario's driving audio as real speech vs placeholder
        tone / silent / corrupted, BEFORE any avatar generation runs."""
        self._audio_validations = {}
        for scenario in scenarios:
            assets = self.dataset_manager.resolve_assets(scenario)
            v = validate_wav(assets.driving_audio, expected_duration_s=scenario.target_duration_s)
            self._audio_validations[scenario.scenario_id] = v
            if not v.valid:
                logger.warning(
                    "Driving audio failed validation",
                    extra={"context": {"scenario": scenario.scenario_id,
                                       "class": v.audio_class, "reason": v.reason}},
                )
        n_valid = sum(v.valid for v in self._audio_validations.values())
        logger.info(
            "Audio validation complete",
            extra={"context": {"scenarios": len(scenarios), "real_speech": n_valid,
                               "invalid": len(scenarios) - n_valid}},
        )

    def build_cases(self, run_dir: Path) -> list[BenchmarkCase]:
        scenarios = self._select_scenarios()
        video_dir = ensure_dir(run_dir / "video")
        cases: list[BenchmarkCase] = []
        adapters = [(aid, create_adapter(aid, device=self.config.device))
                    for aid in self.config.adapters]

        # Gate: never drive a REAL generation model with invalid audio. If every
        # scenario's audio is invalid, stop before generation (goal: no silent
        # continuation on placeholder tones).
        real_adapters = [a for _, a in adapters if getattr(a, "RUNS_IN_VENV", False)]
        if self.config.validate_audio and real_adapters and self._audio_validations:
            if not any(v.valid for v in self._audio_validations.values()):
                reasons = {sid: v.reason for sid, v in self._audio_validations.items()}
                raise BenchmarkError(
                    "All driving audio failed validation — refusing to run avatar "
                    "generation on placeholder/invalid audio. Generate real speech "
                    "with the Voice Engine first.",
                    scenarios=reasons,
                )

        for adapter_id, adapter in adapters:
            gate = self.config.validate_audio and getattr(adapter, "RUNS_IN_VENV", False)
            for scenario in scenarios:
                assets = self.dataset_manager.resolve_assets(scenario)
                skip_reason = None
                if gate:
                    v = self._audio_validations.get(scenario.scenario_id)
                    if v is not None and not v.valid:
                        skip_reason = f"audio validation failed: {v.reason}"
                for rep in range(self.config.repetitions):
                    cases.append(
                        GenerationScenarioCase(
                            adapter, scenario, assets, self.evaluator, video_dir,
                            repetition=rep, skip_reason=skip_reason,
                        )
                    )
        return cases

    # ------------------------------------------------------------------ run
    def run(self) -> tuple[RunResult, dict[str, Path]]:
        run_id = new_run_id("avatar-bench")
        run_dir = ensure_dir(self.config.resolved_output_dir() / run_id)
        cases = self.build_cases(run_dir)
        logger.info(
            "Avatar benchmark starting",
            extra={"context": {"run_id": run_id, "cases": len(cases),
                               "adapters": ",".join(self.config.adapters)}},
        )
        runner = BenchmarkRunner(
            title="Avatar model benchmark",
            config=self.config.to_dict(),
            monitor_resources=self.config.monitor_resources,
        )
        run = runner.run(cases, run_id=run_id)

        reports: dict[str, Path] = {
            "csv": CsvReporter().write(run, run_dir),
            "json": JsonReporter().write(run, run_dir),
            "markdown": AvatarMarkdownReporter().write(run, run_dir),
        }
        if self._audio_validations:
            audio_reports = write_audio_validation_report(
                self._audio_validations.values(), run_dir
            )
            reports["audio_validation"] = audio_reports["markdown"]
        logger.info(
            "Avatar benchmark finished",
            extra={"context": {"run_id": run_id, "report": str(reports["markdown"])}},
        )
        return run, reports
