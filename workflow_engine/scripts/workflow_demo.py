"""Workflow Engine end-to-end demo (Phase C14).

Proves the whole deterministic production pipeline through ONE execution layer:

    prompt -> Storyboard -> Scene Planning -> Voice -> Avatar -> Assets
           -> Media Intelligence -> Editing -> Timeline -> Renderer -> Export

    python -m workflow_engine.scripts.workflow_demo                  # hermetic (mock)
    python -m workflow_engine.scripts.workflow_demo --renderer ffmpeg  # real MP4

It runs the workflow, then verifies the four milestone guarantees:

1. **all stages execute** — the cold run completes every stage and validates;
2. **resume works** — re-running the same run id re-executes nothing (all cached)
   and preserves every artifact's content hash (artifacts preserved);
3. **incremental rebuild works** — changing one presentation setting rebuilds only
   the affected downstream stages, and the incremental planner predicts it exactly;
4. **output playable** — the master + platform exports exist (and probe cleanly
   when ffprobe is available).

Nothing in the Timeline IR or the renderer is modified; the workflow only composes
existing engines. Exit codes: 0 all checks passed, 1 ffmpeg requested but absent,
3 a verification failed.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402

from reel_engine.render import ffprobe_available, probe_media  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from workflow_engine import Presentation, WorkflowEngine  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _print_run(title: str, result, order) -> None:
    print(f"\n{title}")
    for name in order:
        sr = result.stage_results[name]
        arts = ",".join(sr.artifacts)
        print(f"  [{sr.status.value:9}] {name:12} -> {arts}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow Engine end-to-end demo")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "workflow_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    # a fresh run directory each invocation so the demo starts from a clean slate
    run_root = out_dir / args.renderer
    if run_root.exists():
        shutil.rmtree(run_root)
    engine = WorkflowEngine(root=run_root)
    problems: list[str] = []

    # ------------------------------------------------------------- build + validate
    pres = Presentation(theme="finance", soundtrack="upbeat", fps=args.fps,
                        creator="Capital Creators", channel="@capital")
    workflow = engine.build(args.prompt, template=args.template, renderer=args.renderer,
                            presentation=pres, profiles=("reel_9x16", "square_1x1"))
    print(f"Prompt   : {args.prompt!r}")
    print(f"Renderer : {args.renderer}")
    print(f"Pipeline : {' -> '.join(workflow.order())}")
    static = engine.validate(workflow)
    print(f"Static validation: {'OK' if static.ok else 'FAILED'} "
          f"({len(static.warnings)} warnings)")
    if not static.ok:
        problems += static.problems

    # ----------------------------------------------------------- 1) all stages run
    cold = engine.run(workflow, run_id="demo")
    _print_run("Cold run (every stage a cache miss):", cold, workflow.order())
    run_report = engine.validate_result(workflow, cold)
    if not (cold.ok and set(cold.executed()) == set(workflow.order())):
        problems.append("not every stage executed on the cold run")
    if not run_report.ok:
        problems += run_report.problems

    timeline = cold.artifact("timeline").value
    if validate_timeline(timeline) != []:
        problems.append("timeline is invalid")
    print(f"\nTimeline : {timeline.n_scenes} scenes, {timeline.duration_s:.1f}s, "
          f"captions={timeline.has_captions} branding={timeline.has_branding} "
          f"music={timeline.has_music}")

    # ----------------------------------------------------------- 2) resume works
    warm = engine.run(workflow, run_id="demo")
    reused = len(warm.cached())
    print(f"\nResume   : {reused}/{len(workflow.order())} stages reused "
          f"(executed {len(warm.executed())})")
    if reused != len(workflow.order()):
        problems.append("resume re-executed stages that should have been cached")
    for name, art in cold.artifacts.items():          # artifacts preserved
        if warm.artifact(name).content_hash != art.content_hash:
            problems.append(f"resume changed artifact {name!r}")

    # ------------------------------------------------- 3) incremental rebuild works
    changed = engine.build(args.prompt, template=args.template, renderer=args.renderer,
                           presentation=Presentation(theme="dark", soundtrack="cinematic",
                                                     fps=args.fps, creator="Capital Creators",
                                                     channel="@capital"),
                           profiles=("reel_9x16", "square_1x1"))
    plan = engine.incremental_plan(changed, run_id="demo")
    inc = engine.run(changed, run_id="demo")
    _print_run("Incremental run (theme+music changed -> rebuild downstream only):",
               inc, changed.order())
    print(f"  predicted rebuild={sorted(plan.will_run)} reuse={sorted(plan.reuse)} "
          f"(reuse_fraction={plan.reuse_fraction:.0%})")
    if set(plan.will_run) != set(inc.executed()) or set(plan.reuse) != set(inc.cached()):
        problems.append("incremental plan did not match the actual rebuild")
    if not inc.cached():
        problems.append("incremental rebuild reused nothing (expected upstream reuse)")

    # ----------------------------------------------------------- 4) output playable
    master = inc.artifact("master").value
    exports = inc.artifact("exports").value
    outputs = [master, *exports]
    print("\nOutputs:")
    for p in outputs:
        exists = Path(p).exists()
        info = ""
        if exists and ffprobe_available():
            try:
                m = probe_media(p)
                info = f" {m.width}x{m.height} {m.duration_s:.1f}s readable={m.readable}"
            except Exception as exc:  # noqa: BLE001 - probe is best-effort
                info = f" (probe error: {exc})"
        print(f"  [{'OK' if exists else 'MISSING'}] {Path(p).name}{info}")
        if not exists:
            problems.append(f"output not produced: {p}")

    # ------------------------------------------------------------------ verdict
    print("\nChecks:")
    checks = {
        "all stages execute": set(cold.executed()) == set(workflow.order()) and cold.ok,
        "run validates (no missing/orphan/failed)": run_report.ok,
        "resume works (all cached, artifacts preserved)":
            reused == len(workflow.order()),
        "incremental rebuild (downstream only, plan matches)":
            set(plan.will_run) == set(inc.executed()),
        "output playable (master + exports present)":
            all(Path(p).exists() for p in outputs),
    }
    for label, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")

    if problems:
        print("\n=== Workflow Engine demo FAILED ===")
        for p in problems:
            print(f"  - {p}")
        return 3
    print(f"\n=== Workflow Engine demo VALIDATED ({args.renderer}) ===")
    print(f"output dir : {run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
