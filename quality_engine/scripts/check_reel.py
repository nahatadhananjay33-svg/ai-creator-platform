"""Reel Quality Checker CLI (Phase C16).

Run the deterministic quality checks on a rendered reel and print the report.

    # generate a reel through the Workflow Engine (mock) and check it (the gate):
    python -m quality_engine.scripts.check_reel

    # check an already-rendered master (sidecars auto-detected):
    python -m quality_engine.scripts.check_reel --master path/to/master.avi
    python -m quality_engine.scripts.check_reel --master out.mp4 --timeline timeline.json

Hermetic by default: the no-argument path renders with the ``mock`` backend
(stdlib raw-AVI proxy) — no GPU, no ffmpeg, no network. ``--renderer ffmpeg``
produces a real MP4 (needs FFmpeg installed).

Exit codes: 0 = PASS, 2 = FAIL, 1 = usage / environment error.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import PROJECT_ROOT, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402

from reel_engine.render import ffprobe_available  # noqa: E402
from reel_engine.timeline.serde import timeline_from_json  # noqa: E402

from quality_engine import (  # noqa: E402
    QualityChecker,
    QualityConfig,
    ReelArtifacts,
    check_workflow_result,
)

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _config(args) -> QualityConfig:
    return QualityConfig(min_duration_s=args.min_duration,
                         max_duration_s=args.max_duration)


def _check_master(args) -> "tuple[int, object]":
    """Check an already-rendered master file (standalone mode)."""
    master = Path(args.master)
    if not master.exists():
        print(f"FAIL: master not found: {master}")
        return 1, None
    timeline = None
    if args.timeline:
        timeline = timeline_from_json(Path(args.timeline).read_text(encoding="utf-8"))
    artifacts = ReelArtifacts(master_path=master, timeline=timeline,
                              renderer="ffmpeg" if master.suffix == ".mp4" else "mock")
    report = QualityChecker(_config(args)).check(artifacts)
    return 0, report


def _generate_and_check(args) -> "tuple[int, object]":
    """Render a reel through the Workflow Engine, then quality-check the run."""
    from workflow_engine import WorkflowEngine

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1, None

    root = ensure_dir(Path(args.run_dir)) / args.renderer
    if root.exists():
        shutil.rmtree(root)
    engine = WorkflowEngine(root=root)
    workflow = engine.build(args.prompt, template=args.template,
                            renderer=args.renderer, profiles=tuple(args.profiles))
    result = engine.run(workflow, run_id="run")
    print(f"Rendered : {args.renderer}  stages={result.status_counts()}")
    if not result.ok:
        print("FAIL: workflow did not complete; cannot quality-check.")
        return 1, None
    report = check_workflow_result(result, config=_config(args))
    return 0, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reel Quality Checker")
    parser.add_argument("--master", help="check an already-rendered master file")
    parser.add_argument("--timeline", help="timeline JSON for content checks (with --master)")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--profiles", nargs="+", default=["reel_9x16", "square_1x1"])
    parser.add_argument("--min-duration", type=float, default=3.0, dest="min_duration")
    parser.add_argument("--max-duration", type=float, default=90.0, dest="max_duration")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--run-dir",
                        default=str(PROJECT_ROOT / "quality_engine" / "demo_data"))
    args = parser.parse_args(argv)
    configure_logging()

    rc, report = _check_master(args) if args.master else _generate_and_check(args)
    if report is None:
        return rc

    if args.json:
        import json
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print()
        print(report.render_text())
    return 0 if report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
