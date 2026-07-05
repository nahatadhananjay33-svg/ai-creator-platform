"""Human listening evaluation protocol.

Objective metrics catch failures; only humans can rank naturalness, accent
authenticity, and code-switching fluency. This module defines the protocol
and generates blind score sheets from a benchmark run.

Protocol summary
----------------
- >= 3 raters per language; raters must be native/fluent in that language.
- Blind: files are renamed to anonymous ids; rater never sees the model name.
- Each rater scores every (model x prompt) sample on the HUMAN_METRICS
  rubric (1-5). MOS = mean across raters; report with sample count.
- Ties broken by pronunciation score for real-estate categories (entity
  correctness matters more than beauty for Voice AI).
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.exceptions import EvaluationError
from voice_engine.evaluation.criteria import HUMAN_METRICS


@dataclass(frozen=True)
class BlindSample:
    blind_id: str
    subject_id: str  # model — kept only in the hidden key file
    case_id: str
    audio_path: str


class HumanEvalProtocol:
    """Generates blind listening score sheets from a benchmark run."""

    def __init__(self, seed: int = 20260704) -> None:
        self.seed = seed

    def build_blind_set(self, run: RunResult) -> list[BlindSample]:
        samples = [
            BlindSample(
                blind_id="",  # assigned after shuffle
                subject_id=case.subject_id,
                case_id=case.case_id,
                audio_path=case.artifacts.get("audio", ""),
            )
            for case in run.cases
            if case.artifacts.get("audio")
        ]
        if not samples:
            raise EvaluationError("Run contains no audio artifacts to evaluate")
        rng = random.Random(self.seed)
        rng.shuffle(samples)
        return [
            BlindSample(f"sample-{i:03d}", s.subject_id, s.case_id, s.audio_path)
            for i, s in enumerate(samples, start=1)
        ]

    def write_score_sheet(self, run: RunResult, output_dir: Path) -> tuple[Path, Path]:
        """Write rater sheet (no model names) + hidden key file. Returns both paths."""
        output_dir.mkdir(parents=True, exist_ok=True)
        blind = self.build_blind_set(run)

        sheet_path = output_dir / "listening_score_sheet.csv"
        with open(sheet_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["blind_id", "audio_file", *(m.name for m in HUMAN_METRICS), "rater_comments"]
            )
            for sample in blind:
                writer.writerow([sample.blind_id, sample.audio_path, *[""] * len(HUMAN_METRICS), ""])

        key_path = output_dir / "listening_key_CONFIDENTIAL.csv"
        with open(key_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["blind_id", "model", "case_id"])
            for sample in blind:
                writer.writerow([sample.blind_id, sample.subject_id, sample.case_id])

        return sheet_path, key_path
