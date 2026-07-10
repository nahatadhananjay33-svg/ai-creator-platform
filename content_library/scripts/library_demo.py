"""Content Library end-to-end validation demo (Phase C15).

Proves the library manages a project through its whole lifecycle and reproduces its
outputs exactly:

    create project -> generate reel -> save -> reload -> re-render -> verify identical

    python -m content_library.scripts.library_demo                  # hermetic (mock)
    python -m content_library.scripts.library_demo --renderer ffmpeg  # real MP4

Also exercises the content pools (register a brand kit + an asset) and deterministic
search. Nothing leaves the local library directory. Exit codes: 0 all checks passed,
1 ffmpeg requested but absent, 3 a verification failed.
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
from workflow_engine import Presentation  # noqa: E402

from content_library import ContentLibrary, output_hashes  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Content Library end-to-end demo")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--library-dir",
                        default=str(PROJECT_ROOT / "content_library" / "demo_data"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    # a fresh library each run so the demo starts clean
    lib_dir = ensure_dir(Path(args.library_dir))
    root = lib_dir / args.renderer
    if root.exists():
        shutil.rmtree(root)
    library = ContentLibrary(root)
    problems: list[str] = []

    # ---------------------------------------------------------------- create
    project = library.create_project(
        "Investing Early Reel", prompt=args.prompt, template=args.template,
        tags=("finance", "real-estate", "demo"),
        presentation=Presentation(theme="finance", soundtrack="upbeat", fps=args.fps,
                                  creator="Capital Creators", channel="@capital").to_dict())
    print(f"Library  : {root}")
    print(f"Created  : {project.project_id}  (status={project.status})")

    # a brand kit (metadata-only) + a small asset (file) to show the pools
    library.brands.add("Finance Dark Kit", kind="brand_kit", tags=("dark",),
                       meta={"theme": "finance", "soundtrack": "upbeat"})
    logo = root / "cache" / "logo.txt"
    logo.parent.mkdir(parents=True, exist_ok=True)
    logo.write_text("brand-logo-placeholder", encoding="utf-8")
    library.assets.add("Brand Logo", source=logo, kind="image", tags=("brand", "logo"))
    print(f"Pools    : {len(library.brands)} brand kit(s), {len(library.assets)} asset(s)")

    # -------------------------------------------------------------- generate
    outcome = library.generate(project.project_id, renderer=args.renderer)
    rendered = outcome.record
    print(f"\nGenerated: status={rendered.status}  "
          f"stages={outcome.result.status_counts()}")
    print(f"Storyboard: {rendered.storyboard['n_scenes']} scenes "
          f"(provider={rendered.storyboard['provider']})")
    print("Outputs:")
    for o in rendered.outputs:
        p = library.store.project_dir(project.project_id) / o.path
        print(f"  [{'OK' if p.exists() else 'MISSING'}] {o.kind:6} {o.profile or '-':11} "
              f"{o.width}x{o.height} -> {o.path}")
        if not p.exists():
            problems.append(f"output missing: {o.path}")
    hashes_gen = output_hashes(library, rendered)
    ch_gen = {o.path: o.content_hash for o in rendered.outputs}

    # ------------------------------------------------------------ save/reload
    reloaded = library.load(project.project_id)
    if reloaded.to_dict() != rendered.to_dict():
        problems.append("reloaded record differs from the saved record")
    print(f"\nReloaded : record round-trips = {reloaded.to_dict() == rendered.to_dict()}")

    # -------------------------------------------------------------- re-render
    # (a) resume: reuse the cached run -> outputs reproduced verbatim
    resumed = library.rerender(project.project_id)
    print(f"Re-render (resume): stages={resumed.result.status_counts()}")
    hashes_resume = output_hashes(library, resumed.record)

    # (b) force a full re-render of the render stage -> logical identity preserved
    forced = library.generate(project.project_id, renderer=args.renderer, force=("render",))
    print(f"Re-render (forced render): stages={forced.result.status_counts()}")
    hashes_forced = output_hashes(library, forced.record)
    ch_forced = {o.path: o.content_hash for o in forced.record.outputs}

    # -------------------------------------------------------------- verify
    identical_bytes_resume = hashes_gen == hashes_resume
    identical_logical = ch_gen == ch_forced
    identical_bytes_forced = hashes_gen == hashes_forced   # mock renderer is byte-deterministic
    if not identical_bytes_resume:
        problems.append("resume did not reproduce identical output bytes")
    if not identical_logical:
        problems.append("forced re-render changed an output's content hash")
    if args.renderer == "mock" and not identical_bytes_forced:
        problems.append("forced re-render changed output bytes (mock is deterministic)")

    # -------------------------------------------------------------- search
    by_tag = library.search(tag="finance")
    by_status = library.search(status="rendered")
    print(f"\nSearch   : tag=finance -> {[e['project_id'] for e in by_tag]}")
    print(f"           status=rendered -> {[e['project_id'] for e in by_status]}")
    if project.project_id not in {e["project_id"] for e in by_status}:
        problems.append("search did not find the rendered project by status")

    # -------------------------------------------------------------- verdict
    print("\nChecks:")
    checks = {
        "create + generate produced outputs": bool(rendered.outputs) and outcome.result.ok,
        "record round-trips (save -> reload)": reloaded.to_dict() == rendered.to_dict(),
        "re-render (resume) reproduces identical output bytes": identical_bytes_resume,
        "forced re-render preserves logical identity": identical_logical,
        "deterministic search finds the project": bool(by_tag) and bool(by_status),
    }
    for label, ok in checks.items():
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")

    if problems:
        print("\n=== Content Library demo FAILED ===")
        for p in problems:
            print(f"  - {p}")
        return 3
    print(f"\n=== Content Library demo VALIDATED ({args.renderer}) ===")
    print(f"library : {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
