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
        return scenarios

    def build_cases(self, run_dir: Path) -> list[BenchmarkCase]:
        scenarios = self._select_scenarios()
        video_dir = ensure_dir(run_dir / "video")
        cases: list[BenchmarkCase] = []
        for adapter_id in self.config.adapters:
            adapter = create_adapter(adapter_id, device=self.config.device)
            for scenario in scenarios:
                assets = self.dataset_manager.resolve_assets(scenario)
                for rep in range(self.config.repetitions):
                    cases.append(
                        GenerationScenarioCase(
                            adapter, scenario, assets, self.evaluator, video_dir, repetition=rep
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
        logger.info(
            "Avatar benchmark finished",
            extra={"context": {"run_id": run_id, "report": str(reports["markdown"])}},
        )
        return run, reports
