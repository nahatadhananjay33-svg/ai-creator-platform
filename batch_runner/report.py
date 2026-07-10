"""Batch reports: batch_report.json + batch_summary.md (Phase C20).

Both are written from a :class:`~batch_runner.runner.BatchResult` at the end of a
batch: a machine-readable JSON and a human-readable Markdown summary, each
covering total reels, passed / failed / skipped, and generation times.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from batch_runner.runner import BatchResult

REPORT_JSON = "batch_report.json"
SUMMARY_MD = "batch_summary.md"

_STATUS_ICON = {"passed": "✅", "failed": "❌", "skipped": "⤼"}


def _generation_times(result: BatchResult) -> dict[str, Any]:
    """Per-reel durations plus total/average over the reels actually run."""
    run = [o for o in result.outcomes if o.status != "skipped"]
    total = round(sum(o.duration_s for o in run), 3)
    average = round(total / len(run), 3) if run else 0.0
    return {
        "total_s": total,
        "average_s": average,
        "per_reel": {o.name: round(o.duration_s, 3) for o in result.outcomes},
    }


def build_report(result: BatchResult) -> dict[str, Any]:
    """The full machine-readable report as a JSON-able dict."""
    return {
        "total": result.total,
        "passed": result.passed,
        "failed": result.failed,
        "skipped": result.skipped,
        "ok": result.ok,
        "elapsed_s": round(result.elapsed_s, 3),
        "workspace": result.workspace,
        "batch_dir": result.batch_dir,
        "generation_times": _generation_times(result),
        "reels": [
            {
                "name": o.name,
                "status": o.status,
                "code": o.code,
                "error": o.error,
                "duration_s": round(o.duration_s, 3),
                "output_dir": o.output_dir,
            }
            for o in result.outcomes
        ],
    }


def render_summary_md(result: BatchResult) -> str:
    """The human-readable Markdown summary."""
    times = _generation_times(result)
    lines: list[str] = []
    lines.append("# Batch Report")
    lines.append("")
    lines.append(f"**{result.total}** reel(s) — "
                 f"✅ {result.passed} passed · "
                 f"❌ {result.failed} failed · "
                 f"⤼ {result.skipped} skipped")
    lines.append("")
    lines.append(f"- Elapsed: **{round(result.elapsed_s, 1)}s**")
    lines.append(f"- Average per reel (run this batch): "
                 f"**{round(times['average_s'], 1)}s**")
    lines.append(f"- Workspace: `{result.workspace}`")
    lines.append("")
    lines.append("| # | Reel | Status | Time | Output |")
    lines.append("|---|------|--------|------|--------|")
    for i, o in enumerate(result.outcomes, start=1):
        icon = _STATUS_ICON.get(o.status, o.status)
        lines.append(f"| {i} | {o.name} | {icon} {o.status} | "
                     f"{round(o.duration_s, 1)}s | `{o.output_dir}` |")

    failures = [o for o in result.outcomes if o.status == "failed"]
    if failures:
        lines.append("")
        lines.append("## Failures")
        for o in failures:
            reason = o.error or "unknown error"
            lines.append(f"- **{o.name}** — {reason} (see `logs/{o.name}.log`)")

    lines.append("")
    return "\n".join(lines)


def write_reports(result: BatchResult, out_dir: str | Path) -> tuple[Path, Path]:
    """Write both reports into ``out_dir``; return ``(json_path, md_path)``."""
    import json

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / REPORT_JSON
    md_path = out / SUMMARY_MD
    json_path.write_text(json.dumps(build_report(result), indent=2),
                         encoding="utf-8")
    md_path.write_text(render_summary_md(result), encoding="utf-8")
    return json_path, md_path
