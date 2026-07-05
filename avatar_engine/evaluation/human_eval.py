"""Human evaluation protocol for avatar videos.

Automatic metrics catch performance and stability failures; only humans can
judge realism, expressiveness, and the uncanny valley. Same blind protocol
as the voice engine's listening test, adapted to video.

Protocol summary
----------------
- >= 3 raters; raters watch with audio ON (lip-sync judgment needs it).
- Blind: files renamed to anonymous ids; rater never sees the model name.
- Each rater scores every (model x scenario) video on the HUMAN_METRICS
  rubric (1-5). MOS = mean across raters; report with sample count.
- Watch each clip at most twice before scoring; first impressions matter
  for uncanny-valley judgments.
- Hindi scenarios are scored only by Hindi speakers.
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.exceptions import EvaluationError

from avatar_engine.evaluation.criteria import HUMAN_METRICS


@dataclass(frozen=True)
class BlindSample:
    blind_id: str
    subject_id: str  # model — kept only in the hidden key file
    case_id: str
    video_path: str


class AvatarHumanEvalProtocol:
    """Generates blind video score sheets from a benchmark run."""

    def __init__(self, seed: int = 20260704) -> None:
        self.seed = seed

    def build_blind_set(self, run: RunResult) -> list[BlindSample]:
        samples = [
            BlindSample(
                blind_id="",  # assigned after shuffle
                subject_id=case.subject_id,
                case_id=case.case_id,
                video_path=case.artifacts.get("video", ""),
            )
            for case in run.cases
            if case.artifacts.get("video")
        ]
        if not samples:
            raise EvaluationError("Run contains no video artifacts to evaluate")
        rng = random.Random(self.seed)
        rng.shuffle(samples)
        return [
            BlindSample(f"clip-{i:03d}", s.subject_id, s.case_id, s.video_path)
            for i, s in enumerate(samples, start=1)
        ]

    def write_score_sheet(self, run: RunResult, output_dir: Path) -> tuple[Path, Path]:
        """Write rater sheet (no model names) + hidden key file. Returns both paths."""
        output_dir.mkdir(parents=True, exist_ok=True)
        blind = self.build_blind_set(run)

        sheet_path = output_dir / "video_score_sheet.csv"
        with open(sheet_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["blind_id", "video_file", *(m.name for m in HUMAN_METRICS), "rater_comments"]
            )
            for sample in blind:
                writer.writerow([sample.blind_id, sample.video_path, *[""] * len(HUMAN_METRICS), ""])

        key_path = output_dir / "video_key_CONFIDENTIAL.csv"
        with open(key_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["blind_id", "model", "case_id"])
            for sample in blind:
                writer.writerow([sample.blind_id, sample.subject_id, sample.case_id])

        return sheet_path, key_path
