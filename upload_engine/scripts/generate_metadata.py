"""Upload Assistant CLI (Phase C18).

Generate one reel, quality-gate it, and produce upload-ready metadata for it:

    Workflow Engine -> Quality PASS -> Upload Assistant -> metadata.json + upload_preview.md

    # hermetic (mock renderer): generate a reel and its metadata
    python -m upload_engine.scripts.generate_metadata
    python -m upload_engine.scripts.generate_metadata --template finance --prompt "..."
    python -m upload_engine.scripts.generate_metadata --json          # print metadata JSON

Hermetic by default (mock storyboard/voice + mock renderer): no GPU, no ffmpeg, no
OAuth, no network. Nothing is ever posted — the assistant only writes two local
files you copy into each platform yourself.

Exit codes: 0 = metadata written & complete, 2 = quality FAIL or an empty output,
1 = usage / environment error.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402

from reel_engine.render import ffprobe_available  # noqa: E402

from upload_engine import generate_upload_assets  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _generate_reel(args):
    """Render a reel through the Workflow Engine (returns a WorkflowResult or None)."""
    from workflow_engine import WorkflowEngine

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return None, None

    root = ensure_dir(Path(args.run_dir)) / args.renderer
    if root.exists():                        # a clean run each invocation
        shutil.rmtree(root)
    engine = WorkflowEngine(root=root)
    workflow = engine.build(args.prompt, template=args.template,
                            renderer=args.renderer, profiles=tuple(args.profiles))
    result = engine.run(workflow, run_id="reel")
    print(f"Rendered : {args.renderer}  stages={result.status_counts()}")
    if not result.ok:
        print("FAIL: workflow did not complete; cannot generate metadata.")
        return None, None
    return result, root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload Assistant — metadata generator")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--renderer", default="mock", choices=["mock", "ffmpeg"])
    parser.add_argument("--profiles", nargs="+", default=["reel_9x16", "square_1x1"])
    parser.add_argument("--out-dir", default=None,
                        help="where to write metadata.json + upload_preview.md "
                             "(default: <run-dir>/<renderer>/upload)")
    parser.add_argument("--json", action="store_true", help="print the metadata as JSON")
    parser.add_argument("--run-dir", default=str(REEL_OUTPUT_DIR / "upload_assistant"))
    args = parser.parse_args(argv)
    configure_logging()

    # 1) Workflow Engine ----------------------------------------------------
    result, root = _generate_reel(args)
    if result is None:
        return 1 if root is None else 2

    # 2) Quality PASS gate --------------------------------------------------
    from quality_engine import check_workflow_result
    report = check_workflow_result(result)
    print(f"Quality  : {report.overall.name}")
    if not report.ok:
        print("FAIL: reel did not pass quality; not generating upload metadata.")
        return 2

    # 3) Upload Assistant -> 4) metadata.json + 5) upload_preview.md --------
    out_dir = Path(args.out_dir) if args.out_dir else root / "upload"
    metadata, files = generate_upload_assets(result, out_dir, template=args.template)

    # Validation: required fields present, no empty outputs, files written.
    missing = metadata.missing_fields()
    files_ok = files.metadata_json.exists() and files.preview_md.exists()
    print(f"Template : {metadata.template}")
    print(f"Metadata : {files.metadata_json}")
    print(f"Preview  : {files.preview_md}")
    print(f"Title    : {metadata.youtube_title}")
    print(f"Hashtags : {' '.join(metadata.hashtags)}")

    if args.json:
        print("\n" + files.metadata_json.read_text(encoding="utf-8").rstrip())

    ok = files_ok and not missing
    if missing:
        print(f"FAIL: empty required outputs: {', '.join(missing)}")
    if not files_ok:
        print("FAIL: output files were not written.")
    print(f"\n=== UPLOAD METADATA {'GENERATED' if ok else 'CHECK FAILED'} "
          f"({args.renderer}) ===")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
