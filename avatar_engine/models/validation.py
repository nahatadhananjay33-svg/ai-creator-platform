"""Avatar model validation framework (Phase A3.5).

Mirrors ``voice_engine.models.validation``: for an installed adapter (run
inside its venv) verify load, input acceptance, video generation, output
playability, and runtime stability — measuring load time, first-generation
latency, and peak memory. Results serialize to JSON for reports.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.benchmarking import ResourceMonitor
from foundation.logging import get_logger
from foundation.shared_utils import Stopwatch
from foundation.shared_utils.timing import utc_now_iso

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.interface import GenerationRequest
from avatar_engine.models.media import probe_video

logger = get_logger("avatar_engine.models.validation")


@dataclass
class AvatarValidationResult:
    model_id: str
    validated_at: str = field(default_factory=utc_now_iso)
    dependencies_ok: bool = False
    loads: bool = False
    inputs_accepted: bool = False
    video_generated: bool = False
    output_playable: bool = False
    load_time_s: float | None = None
    first_generation_s: float | None = None
    video_duration_s: float | None = None
    video_fps: float | None = None
    video_resolution: str | None = None
    real_time_factor: float | None = None
    peak_rss_mb: float | None = None
    error: str | None = None

    @property
    def valid(self) -> bool:
        return (self.dependencies_ok and self.loads and self.inputs_accepted
                and self.video_generated and self.output_playable)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "valid": self.valid}


class AvatarModelValidator:
    """Runs the standard validation battery against one avatar adapter."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def validate(
        self,
        adapter: BaseAvatarAdapter,
        source_image: Path | None = None,
        driving_audio: Path | None = None,
        driving_video: Path | None = None,
    ) -> AvatarValidationResult:
        result = AvatarValidationResult(model_id=adapter.engine_id)

        result.dependencies_ok = adapter.is_available()
        if not result.dependencies_ok:
            result.error = (
                "dependencies/repo/checkpoints missing — run "
                "python -m avatar_engine.scripts.install_models"
            )
            return result

        monitor = ResourceMonitor(interval_s=1.0).start()
        try:
            try:
                with Stopwatch() as sw:
                    adapter.load()
                result.load_time_s = round(sw.elapsed_s, 2)
                result.loads = True
            except Exception as exc:  # noqa: BLE001
                result.error = f"load failed: {type(exc).__name__}: {str(exc)[:500]}"
                return result

            request = GenerationRequest(
                source_image=source_image,
                driving_audio=driving_audio,
                driving_video=driving_video,
                output_path=self.output_dir / f"{adapter.engine_id}-smoke.mp4",
                scenario_id="validation-smoke",
            )
            try:
                adapter._validate_inputs(request)  # noqa: SLF001 - deliberate reuse
                result.inputs_accepted = True
            except Exception as exc:  # noqa: BLE001
                result.error = f"inputs rejected: {str(exc)[:300]}"
                return result

            try:
                with Stopwatch() as sw:
                    generation = adapter.generate(request)
                result.first_generation_s = round(sw.elapsed_s, 2)
                result.video_generated = generation.video_path.exists()
                probe = probe_video(generation.video_path)
                result.output_playable = probe.readable and probe.frame_count > 0
                result.video_duration_s = probe.duration_s
                result.video_fps = probe.fps
                result.video_resolution = f"{probe.width}x{probe.height}"
                if probe.duration_s > 0:
                    result.real_time_factor = round(sw.elapsed_s / probe.duration_s, 2)
            except Exception as exc:  # noqa: BLE001
                result.error = f"generation failed: {type(exc).__name__}: {str(exc)[:600]}"
        finally:
            monitor.stop()
            if monitor.peak is not None:
                result.peak_rss_mb = round(monitor.peak.rss_mb, 1)
            try:
                adapter.unload()
            except Exception:  # noqa: BLE001
                pass
        return result

    def save(self, result: AvatarValidationResult) -> Path:
        path = self.output_dir / f"{result.model_id}-validation.json"
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path
