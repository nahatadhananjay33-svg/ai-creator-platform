"""Scenario dataset loading, validation, and asset management."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from foundation.config import load_yaml
from foundation.exceptions import ConfigError, DatasetError
from foundation.logging import get_logger
from foundation.shared_utils import generate_sine_wav, write_wav
from foundation.shared_utils.video_io import generate_test_pattern_video

from avatar_engine.datasets.schema import (
    AvatarScenario,
    EvaluationFocus,
    ScenarioCategory,
    ScenarioDataset,
)

logger = get_logger("avatar_engine.datasets")

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_ASSETS_DIR = DEFAULT_DATA_DIR / "assets"
_SCENARIO_FILE = "scenarios.yaml"

#: Categories every valid dataset must cover (core evaluation dimensions).
_REQUIRED_CATEGORIES = {
    ScenarioCategory.NEUTRAL_SPEECH,
    ScenarioCategory.LONG_NARRATION,
    ScenarioCategory.FAST_SPEECH,
    ScenarioCategory.SILENCE_SEGMENTS,
}


@dataclass(frozen=True)
class ResolvedAssets:
    """Absolute asset paths for one scenario after resolution."""

    source_image: Path
    driving_audio: Path
    #: Driving video for video-driven models (LivePortrait); None when absent.
    driving_video: Path | None = None


class AvatarDatasetManager:
    """Loads, validates, and serves avatar benchmark scenarios."""

    def __init__(self, data_dir: Path | None = None, assets_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.assets_dir = assets_dir or (self.data_dir / "assets")

    # ------------------------------------------------------------------ loading
    def load(self) -> ScenarioDataset:
        path = self.data_dir / _SCENARIO_FILE
        try:
            raw = load_yaml(path)
        except ConfigError as exc:
            raise DatasetError(f"Scenario file missing or unreadable: {path}") from exc
        try:
            dataset = ScenarioDataset(
                description=raw.get("description", ""),
                version=str(raw.get("version", "0")),
            )
            for entry in raw["scenarios"]:
                dataset.scenarios.append(
                    AvatarScenario(
                        scenario_id=entry["id"],
                        category=ScenarioCategory(entry["category"]),
                        script_text=entry["script"].strip(),
                        language=entry.get("language", "en"),
                        target_duration_s=float(entry["target_duration_s"]),
                        source_image=entry.get("source_image", ""),
                        driving_audio=entry.get("driving_audio", ""),
                        driving_video=entry.get("driving_video", ""),
                        evaluation_focus=tuple(
                            EvaluationFocus(f) for f in entry.get("evaluation_focus", [])
                        ),
                        notes=entry.get("notes", ""),
                    )
                )
        except (KeyError, ValueError) as exc:
            raise DatasetError(f"Malformed scenario file: {path}") from exc
        problems = self.validate(dataset)
        if problems:
            raise DatasetError(
                f"Scenario validation failed: {problems[:3]}", problem_count=len(problems)
            )
        logger.info(
            "Scenario dataset loaded",
            extra={"context": {"scenarios": len(dataset.scenarios), "version": dataset.version}},
        )
        return dataset

    @staticmethod
    def validate(dataset: ScenarioDataset) -> list[str]:
        """Structural validation. Returns problem descriptions."""
        problems: list[str] = []
        seen: set[str] = set()
        for s in dataset.scenarios:
            if s.scenario_id in seen:
                problems.append(f"duplicate id: {s.scenario_id}")
            seen.add(s.scenario_id)
            if not s.script_text and s.category is not ScenarioCategory.SILENCE_SEGMENTS:
                problems.append(f"empty script: {s.scenario_id}")
            if s.target_duration_s <= 0:
                problems.append(f"non-positive duration: {s.scenario_id}")
            if not s.evaluation_focus:
                problems.append(f"no evaluation focus: {s.scenario_id}")
        missing = _REQUIRED_CATEGORIES - dataset.categories()
        if missing:
            problems.append(
                f"missing required categories: {sorted(c.value for c in missing)}"
            )
        return problems

    # ------------------------------------------------------------------ assets
    def resolve_assets(self, scenario: AvatarScenario) -> ResolvedAssets:
        """Absolute asset paths for a scenario (defaults when unset)."""
        image = scenario.source_image or "default_portrait.png"
        audio = scenario.driving_audio or f"{scenario.scenario_id}.wav"
        # Driving video is optional: a per-scenario override, else a shared
        # "driving_video.mp4". Only present when video-driven models need it.
        video = self.assets_dir / (scenario.driving_video or "driving_video.mp4")
        return ResolvedAssets(
            source_image=self.assets_dir / image,
            driving_audio=self.assets_dir / audio,
            driving_video=video if video.exists() else None,
        )

    def missing_assets(self, dataset: ScenarioDataset) -> dict[str, list[str]]:
        """scenario_id -> missing asset paths. Empty dict = ready to benchmark."""
        missing: dict[str, list[str]] = {}
        for scenario in dataset.scenarios:
            assets = self.resolve_assets(scenario)
            gone = [
                str(p) for p in (assets.source_image, assets.driving_audio) if not p.exists()
            ]
            if gone:
                missing[scenario.scenario_id] = gone
        return missing

    def generate_placeholder_assets(self, dataset: ScenarioDataset) -> list[Path]:
        """Create synthetic stand-in assets for every missing file.

        Placeholders (sine-tone WAVs at the scenario's target duration and a
        test-pattern 'portrait') let the pipeline run end-to-end before real
        portraits/voice-engine audio are produced. Real assets simply replace
        the files — see ``data/assets/README.md``.
        """
        created: list[Path] = []
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        for scenario in dataset.scenarios:
            assets = self.resolve_assets(scenario)
            if not assets.driving_audio.exists():
                tone = generate_sine_wav(
                    duration_s=min(scenario.target_duration_s, 10.0), frequency_hz=220.0
                )
                write_wav(assets.driving_audio, tone)
                created.append(assets.driving_audio)
            if not assets.source_image.exists():
                if assets.source_image.suffix.lower() == ".avi":
                    generate_test_pattern_video(assets.source_image, n_frames=1)
                    created.append(assets.source_image)
                else:
                    _write_placeholder_png(assets.source_image)
                    created.append(assets.source_image)
        if created:
            logger.info(
                "Placeholder assets generated",
                extra={"context": {"count": len(created), "dir": str(self.assets_dir)}},
            )
        return created


def _write_placeholder_png(path: Path, size: int = 128) -> None:
    """Write a valid flat-gray RGB PNG with the stdlib only."""
    import struct
    import zlib

    def png_chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    row = b"\x00" + b"\x80\x80\x80" * size  # filter 0 + gray pixels
    idat = zlib.compress(row * size)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", idat)
        + png_chunk(b"IEND", b"")
    )
