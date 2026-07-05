"""Avatar benchmark configuration schema and defaults."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.constants.paths import AVATAR_ENGINE_DIR


@dataclass
class AvatarBenchmarkConfig:
    """Configuration for one benchmark run (bindable via ConfigLoader)."""

    adapters: list[str] = field(default_factory=lambda: ["mock"])
    categories: list[str] = field(default_factory=list)  # empty = all categories
    #: 0 = no cap. Caps scenarios per category for smoke runs.
    max_scenarios: int = 0
    repetitions: int = 1
    device: str = "auto"
    output_dir: str = str(AVATAR_ENGINE_DIR / "output" / "runs")
    #: Override the assets directory (defaults to the dataset's own).
    assets_dir: str | None = None
    #: Generate synthetic stand-ins for missing assets instead of failing.
    allow_placeholder_assets: bool = True
    #: Verify driving audio is real speech before avatar generation (A3.8.5).
    #: When True, real generation models skip any scenario whose audio is a
    #: placeholder tone / silent / corrupted — the benchmark never drives a
    #: model with invalid audio. The mock adapter (a wiring double) is exempt.
    validate_audio: bool = True
    monitor_resources: bool = True

    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
