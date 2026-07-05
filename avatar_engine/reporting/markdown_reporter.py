"""Markdown run report: measured results plus research context.

Combines run measurements with static catalog knowledge (license, hardware,
maintenance) so a single file answers "which model should we use?" —
mirrors the voice engine's Markdown reporter.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.reporting import Reporter, summarize_run

from avatar_engine.research.catalog import CANDIDATE_PROFILES

_KEY_METRICS = (
    ("real_time_factor", "RTF"),
    ("output_fps", "FPS"),
    ("identity_similarity", "Identity"),
    ("lip_sync_confidence", "LSE-C"),
    ("flicker_index", "Flicker"),
    ("frozen_frame_ratio", "Frozen"),
    ("peak_rss_mb", "Peak RAM (MB)"),
    ("peak_gpu_mem_mb", "Peak VRAM (MB)"),
)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:g}"


class AvatarMarkdownReporter(Reporter):
    def write(self, run: RunResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        summary = summarize_run(run)
        lines: list[str] = []

        lines.append(f"# Avatar Benchmark Report — `{run.run_id}`")
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

        if run.config.get("allow_placeholder_assets"):
            lines.append(
                "> **Note:** placeholder assets were permitted for this run. If any "
                "scenario used them, treat its metrics as pipeline-wiring checks only."
            )
            lines.append("")

        lines.append("## Results by model (automatic metrics)")
        lines.append("")
        header = "| Model | Cases | Pass | Fail | Skip | " + " | ".join(h for _, h in _KEY_METRICS) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (5 + len(_KEY_METRICS)))
        for s in summary.subjects:
            cells = [
                s.subject_id, str(s.total_cases), str(s.passed), str(s.failed), str(s.skipped),
                *[_fmt(s.metric_means.get(name)) for name, _ in _KEY_METRICS],
            ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
        lines.append(
            "> All values above are **automatically measured** means over passed cases. "
            "Perceptual quality (realism, expression, uncanny valley) requires the human "
            "protocol — see `video_score_sheet.csv` when generated."
        )
        lines.append("")

        lines.append("## Model context (static research metadata)")
        lines.append("")
        lines.append("| Model | Task | License (weights) | Commercial | Min VRAM | Maintenance |")
        lines.append("|---|---|---|---|---|---|")
        for s in summary.subjects:
            profile = CANDIDATE_PROFILES.get(s.subject_id)
            if profile is None:
                continue
            vram = profile.spec.hardware.min_vram_gb
            lines.append(
                "| {} | {} | {} | {} | {} | {} |".format(
                    profile.display_name,
                    profile.task.value,
                    profile.spec.license.weights_license,
                    "yes" if profile.spec.license.commercial_use else "NO",
                    f"{vram:g} GB" if vram else "CPU-capable",
                    profile.activity.maintenance.value,
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
