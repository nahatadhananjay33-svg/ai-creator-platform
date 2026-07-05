"""Benchmark configuration schema and defaults."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from foundation.constants import Language
from foundation.constants.paths import BENCHMARK_OUTPUT_DIR


@dataclass
class VoiceBenchmarkConfig:
    """Configuration for one benchmark run (bindable via ConfigLoader)."""

    adapters: list[str] = field(default_factory=lambda: ["mock"])
    languages: list[str] = field(default_factory=lambda: ["en", "hi", "hi-en", "bn"])
    categories: list[str] = field(default_factory=list)  # empty = all categories
    #: 0 = no cap. CPU-only machines cap items per language to keep slow
    #: models' runs tractable; the report records the effective scope.
    max_items_per_language: int = 0
    repetitions: int = 1
    include_streaming_scenario: bool = True
    reference_audio: str | None = None  # path to cloning reference WAV
    reference_text: str = ""            # transcript of the reference audio
    device: str = "auto"
    output_dir: str = str(BENCHMARK_OUTPUT_DIR)
    monitor_resources: bool = True

    def resolved_languages(self) -> list[Language]:
        return [Language.from_code(code) for code in self.languages]

    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
