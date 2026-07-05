"""Benchmark case implementations."""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.exceptions import AdapterNotAvailableError

from avatar_engine.datasets.manager import ResolvedAssets
from avatar_engine.datasets.schema import AvatarScenario
from avatar_engine.evaluation import GenerationEvaluator
from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.interface import GenerationRequest


class GenerationScenarioCase(BenchmarkCase):
    """One adapter generating one scenario's avatar video."""

    def __init__(
        self,
        adapter: BaseAvatarAdapter,
        scenario: AvatarScenario,
        assets: ResolvedAssets,
        evaluator: GenerationEvaluator,
        output_dir: Path,
        repetition: int = 0,
        skip_reason: str | None = None,
    ) -> None:
        suffix = f"-r{repetition}" if repetition else ""
        super().__init__(
            case_id=f"{adapter.engine_id}-{scenario.scenario_id}{suffix}",
            subject_id=adapter.engine_id,
            scenario=scenario.category.value,
        )
        self.adapter = adapter
        self.avatar_scenario = scenario
        self.assets = assets
        self.evaluator = evaluator
        self.output_dir = output_dir
        #: When set (e.g. failed audio validation), the case is SKIPPED with this
        #: reason before any generation runs — the model never sees bad audio.
        self.skip_reason = skip_reason

    def execute(self, result: CaseResult) -> None:
        if self.skip_reason:
            raise AdapterNotAvailableError(self.skip_reason, adapter=self.adapter.engine_id)
        request = GenerationRequest(
            source_image=self.assets.source_image,
            driving_audio=self.assets.driving_audio,
            output_path=self.output_dir / f"{self.case_id}.mp4",
            scenario_id=self.avatar_scenario.scenario_id,
        )
        generation = self.adapter.generate(request)
        result.artifacts["video"] = str(generation.video_path)
        result.metadata["scenario_id"] = self.avatar_scenario.scenario_id
        result.metadata["language"] = self.avatar_scenario.language
        result.metadata["evaluation_focus"] = [
            f.value for f in self.avatar_scenario.evaluation_focus
        ]
        for measurement in self.evaluator.evaluate(generation, self.avatar_scenario, self.assets):
            result.add(measurement)
        # Static context so single-run artifacts stay self-describing.
        result.add(
            Measurement(
                "commercial_use_ok",
                self.adapter.spec.license.commercial_use,
                source="static",
                notes=self.adapter.spec.license.weights_license,
            )
        )
