"""Automatic model-comparison report (A3.9): SadTalker vs LivePortrait.

Pure aggregation over existing benchmark ``RunResult``s — no new metrics, no
subjective judgement. Consumes one or more runs (the framework's own JSON
output) and emits a side-by-side markdown + JSON of the **measured** numbers.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.reporting import summarize_run
from foundation.shared_utils.timing import utc_now_iso

#: (measurement name -> label). Only metrics the framework already produces.
_METRICS = (
    ("generation_time_s", "Generation time (s)"),
    ("real_time_factor", "RTF (gen/dur)"),
    ("output_fps", "FPS"),
    ("video_duration_s", "Video duration (s)"),
    ("output_width", "Width (px)"),
    ("output_height", "Height (px)"),
    ("peak_gpu_mem_mb", "Peak VRAM (MB)"),
    ("avg_gpu_mem_mb", "Avg VRAM (MB)"),
    ("gpu_utilization_percent", "GPU util (%)"),
    ("gpu_temp_c", "GPU temp (C)"),
    ("peak_rss_mb", "Peak RAM (MB)"),
    ("identity_similarity", "Identity similarity"),
    ("lip_sync_confidence", "Lip-sync confidence"),
    ("flicker_index", "Flicker index"),
    ("frozen_frame_ratio", "Frozen-frame ratio"),
    ("mean_sharpness", "Mean sharpness"),
)


@dataclass
class ModelSummary:
    model_id: str
    device: str
    total_cases: int
    passed: int
    failed: int
    skipped: int
    success_rate: float          # passed / executed
    output_size_kb: float | None  # mean produced-video size
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _mean_output_kb(cases) -> float | None:
    sizes = []
    for c in cases:
        path = c.artifacts.get("video")
        if path and Path(path).exists():
            sizes.append(Path(path).stat().st_size / 1024)
    return round(sum(sizes) / len(sizes), 1) if sizes else None


def build_comparison(runs: list[RunResult]) -> list[ModelSummary]:
    """One ModelSummary per (run, subject). Merges multiple runs."""
    summaries: list[ModelSummary] = []
    for run in runs:
        cases_by_subject = run.by_subject()
        rsum = summarize_run(run)
        for s in rsum.subjects:
            cases = cases_by_subject.get(s.subject_id, [])
            device = next((str(c.get_value("device")) for c in cases
                           if c.get_value("device")), "—")
            executed = s.total_cases - s.skipped
            summaries.append(ModelSummary(
                model_id=s.subject_id, device=device, total_cases=s.total_cases,
                passed=s.passed, failed=s.failed, skipped=s.skipped,
                success_rate=round(s.passed / executed, 3) if executed else 0.0,
                output_size_kb=_mean_output_kb(cases),
                metrics={name: s.metric_means[name] for name, _ in _METRICS
                         if name in s.metric_means},
            ))
    return summaries


def write_comparison_report(runs: list[RunResult], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = build_comparison(runs)
    generated_at = utc_now_iso()

    json_path = out_dir / "model_comparison_report.json"
    json_path.write_text(
        json.dumps({"generated_at": generated_at, "models": [s.to_dict() for s in summaries]},
                   ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    models = [s.model_id for s in summaries]
    lines = [
        "# Avatar Model Comparison", "",
        f"Generated: {generated_at}", "",
        f"Models compared: {', '.join(models) if models else '—'}.", "",
        "All values are **measured** means over passed cases from the existing "
        "benchmark framework — no subjective judgement.", "",
        "> Note: SadTalker and MuseTalk are **audio-driven** (lip-sync to the "
        "scenario speech) while LivePortrait is **video-driven** (reenacts from a "
        "driving clip). They share the same source portraits and scenarios; audio "
        "lip-sync metrics are only meaningful for the audio-driven models.", "",
        "| Metric | " + " | ".join(models) + " |",
        "|" + "---|" * (len(models) + 1),
    ]

    def row(label, values):
        cells = [("—" if v is None else (f"{v:g}" if isinstance(v, (int, float)) else str(v)))
                 for v in values]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    row("Device", [s.device for s in summaries])
    row("Cases (pass/fail/skip)",
        [f"{s.passed}/{s.failed}/{s.skipped}" for s in summaries])
    row("Success rate", [s.success_rate for s in summaries])
    row("Output size (KB)", [s.output_size_kb for s in summaries])
    for name, label in _METRICS:
        row(label, [s.metrics.get(name) for s in summaries])

    lines.append("")
    md_path = out_dir / "model_comparison_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
