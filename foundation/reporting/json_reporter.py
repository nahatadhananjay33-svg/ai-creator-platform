"""JSON report: full run dump plus machine-readable summary."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from foundation.benchmarking import RunResult
from foundation.reporting.base import Reporter
from foundation.reporting.summary import summarize_run


class JsonReporter(Reporter):
    def write(self, run: RunResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        full_path = output_dir / "run_full.json"
        run.save_json(full_path)

        summary = summarize_run(run)
        summary_path = output_dir / "run_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": summary.run_id,
                    "title": summary.title,
                    "subjects": [asdict(s) for s in summary.subjects],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return full_path
