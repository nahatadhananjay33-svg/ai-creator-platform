"""Markdown report: human-readable comparison with model context.

Combines run measurements with static ModelSpec knowledge (license,
hardware, strengths/weaknesses from capabilities notes) so a single file
answers "which model should we use?".
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import RunResult
from voice_engine.adapters.registry import ADAPTER_CLASSES
from voice_engine.reporting.base import Reporter
from voice_engine.reporting.summary import SubjectSummary, summarize_run

_KEY_METRICS = (
    ("real_time_factor", "RTF", False),
    ("first_chunk_latency_s", "First-chunk (s)", False),
    ("speaker_similarity", "Similarity", True),
    ("silence_ratio", "Silence", False),
    ("clipping_ratio", "Clipping", False),
    ("peak_rss_mb", "Peak RAM (MB)", False),
)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


class MarkdownReporter(Reporter):
    def write(self, run: RunResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = summarize_run(run)
        lines: list[str] = []

        lines.append(f"# Voice Benchmark Report — `{run.run_id}`")
        lines.append("")
        lines.append(f"**Title:** {run.title}  ")
        lines.append(f"**Started:** {run.started_at}  ")
        lines.append(f"**Finished:** {run.finished_at or 'n/a'}")
        lines.append("")

        env = run.environment
        gpus = env.get("gpus") or []
        gpu_desc = ", ".join(g.get("name", "?") for g in gpus) if gpus else "none"
        lines.append("## Environment")
        lines.append("")
        lines.append(f"- OS: {env.get('os_name', '?')} {env.get('os_version', '')}")
        lines.append(f"- CPU: {env.get('cpu_name', '?')} ({env.get('cpu_cores_logical', '?')} logical cores)")
        ram = env.get("ram_total_mb")
        lines.append(f"- RAM: {round(ram / 1024, 1) if ram else '?'} GB")
        lines.append(f"- GPU: {gpu_desc}")
        lines.append(f"- Python: {env.get('python_version', '?')}")
        lines.append("")

        lines.append("## Results by model (automatic metrics)")
        lines.append("")
        header = "| Model | Cases | Pass | Fail | Skip | " + " | ".join(h for _, h, _ in _KEY_METRICS) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (5 + len(_KEY_METRICS)))
        for s in summary.subjects:
            cells = [
                s.subject_id, str(s.total_cases), str(s.passed), str(s.failed), str(s.skipped),
                *[_fmt(s.metric_means.get(name)) for name, _, _ in _KEY_METRICS],
            ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        lines.append(
            "> All values above are **automatically measured** means over passed cases. "
            "Perceptual quality (naturalness, accent, code-switching) requires the human "
            "listening protocol — see `listening_score_sheet.csv` when generated."
        )
        lines.append("")

        lines.append("## Model context (static research metadata)")
        lines.append("")
        lines.append("| Model | License (weights) | Commercial | Min VRAM | CPU real-time | Streaming | Cloning |")
        lines.append("|---|---|---|---|---|---|---|")
        for s in summary.subjects:
            cls = ADAPTER_CLASSES.get(s.subject_id)
            if cls is None:
                continue
            spec, caps = cls.SPEC, cls.CAPABILITIES
            vram = spec.hardware.min_vram_gb
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} |".format(
                    spec.display_name,
                    spec.license.weights_license,
                    "yes" if spec.license.commercial_use else "NO",
                    f"{vram:g} GB" if vram else "CPU-only OK",
                    "yes" if caps.cpu_realtime else "no",
                    caps.streaming.value,
                    "zero-shot" if caps.zero_shot_cloning else "none",
                )
            )
        lines.append("")

        failures = [c for c in run.cases if c.error]
        if failures:
            lines.append("## Failures and skips")
            lines.append("")
            for case in failures:
                lines.append(f"- `{case.case_id}` ({case.subject_id}, {case.status.value}): {case.error}")
            lines.append("")

        path = output_dir / "report.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
