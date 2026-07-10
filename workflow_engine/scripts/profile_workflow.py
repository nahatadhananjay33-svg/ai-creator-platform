"""Workflow profiler + performance validation CLI (Phase C17).

Generates the SAME reel twice and reports per-stage timing for each run, proving
the three performance guarantees:

    1. the second run is faster   (the workflow cache reuses completed stages);
    2. the output is identical     (byte-for-byte — the master + exports don't change);
    3. quality still PASSES        (the C16 Quality Checker still says PASS).

    python -m workflow_engine.scripts.profile_workflow                  # hermetic (mock)
    python -m workflow_engine.scripts.profile_workflow --renderer ffmpeg  # real MP4

Hermetic by default (mock storyboard/voice + mock renderer): no GPU, no ffmpeg, no
network. Exit codes: 0 = all guarantees held, 2 = a guarantee failed, 1 =
usage/environment error.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import Stopwatch  # noqa: E402
from foundation.shared_utils.hashing import sha256_file  # noqa: E402

from reel_engine.render import ffprobe_available  # noqa: E402

from workflow_engine import WorkflowEngine  # noqa: E402
from workflow_engine.timing import StageTiming, WorkflowTiming  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _output_hashes(result) -> dict[str, str]:
    """SHA-256 of the master + every export file the run produced."""
    hashes: dict[str, str] = {}
    master = Path(result.artifact("master").value)
    if master.exists():
        hashes["master"] = sha256_file(master)
    for e in result.artifact("master").meta.get("exports", []):
        p = Path(e["path"])
        if p.exists():
            hashes[f"export:{e.get('profile', p.name)}"] = sha256_file(p)
    return hashes


def _profile_run(engine, workflow, *, run_id: str, config):
    """Run (or resume) the workflow, then quality-check it — timing the quality pass.

    Returns (result, WorkflowTiming, quality_report, output_hashes)."""
    from quality_engine import check_workflow_result  # lazy: avoids an import cycle

    result = engine.run(workflow, run_id=run_id)
    with Stopwatch() as sw:
        report = check_workflow_result(result)
    quality_row = StageTiming(label="Quality", seconds=round(sw.elapsed_s, 4),
                              status="measured")
    timing = WorkflowTiming.from_result(result, extra_rows=(quality_row,))
    return result, timing, report, _output_hashes(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow performance profiler")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--profiles", nargs="+", default=["reel_9x16", "square_1x1"])
    parser.add_argument("--json", action="store_true", help="also print JSON timings")
    parser.add_argument("--run-dir",
                        default=str(REEL_OUTPUT_DIR / "profile_workflow"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    root = ensure_dir(Path(args.run_dir)) / args.renderer
    if root.exists():                       # a clean cold run each invocation
        shutil.rmtree(root)
    engine = WorkflowEngine(root=root)
    workflow = engine.build(args.prompt, template=args.template,
                            renderer=args.renderer, profiles=tuple(args.profiles))

    print(f"Prompt   : {args.prompt!r}")
    print(f"Renderer : {args.renderer}")
    print(f"Pipeline : {' -> '.join(workflow.order())}\n")

    # ---- Run 1: cold (every stage executes) ---------------------------------
    _, cold_t, cold_q, cold_h = _profile_run(engine, workflow, run_id="reel",
                                             config=None)
    print(cold_t.render_text(title="Run 1 — cold (all stages execute)"))
    print(f"  quality: {cold_q.overall.name}\n")

    # ---- Run 2: warm (cache reuses completed stages) ------------------------
    _, warm_t, warm_q, warm_h = _profile_run(engine, workflow, run_id="reel",
                                             config=None)
    print(warm_t.render_text(title="Run 2 — warm (workflow cache reuses stages)"))
    print(f"  quality: {warm_q.overall.name}\n")

    # ---- verdict ------------------------------------------------------------
    faster = warm_t.total_s < cold_t.total_s
    identical = cold_h == warm_h and bool(cold_h)
    quality_ok = cold_q.ok and warm_q.ok
    speedup = (cold_t.total_s / warm_t.total_s) if warm_t.total_s > 0 else float("inf")

    print("Performance guarantees:")
    print(f"  [{'OK' if faster else 'FAIL'}] second run faster "
          f"({cold_t.total_s:.2f}s -> {warm_t.total_s:.2f}s, "
          f"{speedup:.1f}x; {warm_t.n_reused} stages reused)")
    print(f"  [{'OK' if identical else 'FAIL'}] output identical "
          f"({len(cold_h)} files, byte-for-byte)")
    print(f"  [{'OK' if quality_ok else 'FAIL'}] quality still PASS")

    if args.json:
        import json
        print("\nJSON:")
        print(json.dumps({"cold": cold_t.to_dict(), "warm": warm_t.to_dict(),
                          "speedup": round(speedup, 3), "identical": identical},
                         indent=2))

    ok = faster and identical and quality_ok
    print(f"\n=== {'PERFORMANCE VALIDATED' if ok else 'PERFORMANCE CHECK FAILED'} "
          f"({args.renderer}) ===")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
