"""The single Version 1.0 command (Phase C19):

    python -m creator.run

One command takes a prompt all the way to upload-ready files:

    Prompt  ->  Workflow  ->  Quality  ->  Upload Metadata  ->  Finished

It composes engines that already exist — the Workflow Engine builds the reel,
the Quality Engine gates it PASS/FAIL, and the Upload Assistant writes
``metadata.json`` + ``upload_preview.md`` — and lands everything in one
standardized workspace (see :mod:`creator.paths`).

Everything is single-user and local. Hermetic by default (``--renderer mock``:
no GPU, no FFmpeg, no network); nothing is ever posted anywhere — you copy the
generated captions into each platform yourself.

Examples::

    python -m creator.run
    python -m creator.run --prompt "5 tips for first-time home buyers" --template real_estate
    python -m creator.run --renderer ffmpeg            # real MP4s (needs FFmpeg)
    python -m creator.run --config my_channel.yaml     # your saved settings
    python -m creator.run --json                       # also print metadata JSON

Exit codes: 0 = reel generated, passed quality, metadata written;
2 = quality FAIL (with the gate on) or empty/insufficient output;
1 = a user/environment mistake (shown as a plain message, no traceback).
"""
from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import Any

from foundation.logging import configure_logging
from foundation.shared_utils.text import slugify

from creator.config import CreatorConfig, load_creator_config
from creator.paths import Workspace, resolve_workspace


# --------------------------------------------------------------------------- #
# Argument parsing + config resolution
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m creator.run",
        description="Generate one upload-ready reel from a prompt, end to end.",
    )
    parser.add_argument("--prompt", default=None, help="the idea for your reel")
    parser.add_argument("--template", default=None,
                        help="content vertical (real_estate, finance, education, ...)")
    parser.add_argument("--renderer", default=None, choices=["mock", "ffmpeg"],
                        help="mock (fast, no deps) or ffmpeg (real MP4s)")
    parser.add_argument("--profiles", nargs="+", default=None,
                        help="export aspect ratios (reel_9x16 square_1x1 landscape_16x9)")
    parser.add_argument("--language", default=None, help="narration/caption language (en, hi, ...)")
    parser.add_argument("--config", default=None,
                        help="a YAML config file layered on top of the defaults")
    parser.add_argument("--workspace", default=None,
                        help="workspace root (default: <repo>/workspace)")
    parser.add_argument("--name", default=None,
                        help="run name / folder (default: a slug of the prompt)")
    parser.add_argument("--no-quality-gate", action="store_true",
                        help="write metadata even if the reel fails the quality check")
    parser.add_argument("--json", action="store_true", help="also print the metadata as JSON")
    parser.add_argument("--quiet", action="store_true", help="print only the final result")
    parser.add_argument("--verbose", action="store_true",
                        help="show detailed engine logs (INFO level) on stderr")
    return parser


def _resolve_config(args: argparse.Namespace) -> CreatorConfig:
    """Load the layered config, then fold in any explicit command-line flags."""
    overrides: dict[str, Any] = {}
    gen: dict[str, Any] = {}
    if args.prompt is not None:
        gen["prompt"] = args.prompt
    if args.template is not None:
        gen["template"] = args.template
    if args.renderer is not None:
        gen["renderer"] = args.renderer
    if args.profiles is not None:
        gen["profiles"] = list(args.profiles)
    if args.language is not None:
        gen["language"] = args.language
    if gen:
        overrides["generation"] = gen
    if args.workspace is not None:
        overrides["paths"] = {"root": args.workspace}
    if args.no_quality_gate:
        overrides["quality"] = {"gate": False}
    return load_creator_config(config_path=args.config, overrides=overrides)


def _run_id_for(cfg: CreatorConfig, name: str | None) -> str:
    """A deterministic, filesystem-safe run id (repeat runs reuse the folder)."""
    return slugify(name or cfg.prompt) or "reel"


# --------------------------------------------------------------------------- #
# The four steps
# --------------------------------------------------------------------------- #
def _step_workflow(cfg: CreatorConfig, ws: Workspace, run_id: str):
    """Prompt -> Workflow: build and run the reel under workspace/projects/<id>."""
    from workflow_engine import WorkflowEngine
    from workflow_engine.stages.base import Presentation

    engine = WorkflowEngine(root=ws.projects)
    run_dir = engine.run_dir(run_id)
    if run_dir.exists():                         # a clean run each invocation
        shutil.rmtree(run_dir)
    presentation = Presentation(creator=cfg.creator, channel=cfg.channel)
    workflow = engine.build(
        cfg.prompt,
        template=cfg.template,
        renderer=cfg.renderer,
        profiles=cfg.profiles,
        language=cfg.language,
        presentation=presentation,
    )
    result = engine.run(workflow, run_id=run_id)
    return result, run_dir


def _step_quality(result):
    """Quality gate the finished reel."""
    from quality_engine import check_workflow_result

    return check_workflow_result(result)


def _step_upload(cfg: CreatorConfig, result, ws: Workspace, run_id: str):
    """Upload Metadata: write metadata.json + upload_preview.md, and copy the
    finished renditions, into workspace/exports/<id>."""
    from upload_engine import generate_upload_assets

    out_dir = ws.exports / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    metadata, files = generate_upload_assets(result, out_dir, template=cfg.template)

    # Copy the finished export renditions next to their metadata so the whole
    # upload bundle lives in one folder.
    copied: list[Path] = []
    try:
        exports = result.artifact("exports").value
    except Exception:
        exports = ()
    for src in exports or ():
        src = Path(src)
        if src.exists():
            dest = out_dir / src.name
            shutil.copy2(src, dest)
            copied.append(dest)
    return metadata, files, out_dir, copied


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run(cfg: CreatorConfig, *, name: str | None = None, as_json: bool = False,
        quiet: bool = False) -> int:
    """Run the full Prompt -> Workflow -> Quality -> Upload -> Finished flow."""
    ws = resolve_workspace(cfg.workspace_root).ensure()
    run_id = _run_id_for(cfg, name)

    def say(msg: str = "") -> None:
        if not quiet:
            print(msg)

    say("AI Creator Platform — v1.0")
    say(f'Prompt   : "{cfg.prompt}"')
    say(f"Template : {cfg.template}  |  Renderer: {cfg.renderer}  "
        f"|  Profiles: {', '.join(cfg.profiles)}")
    say(f"Workspace: {ws.root}")
    say()

    # 1) Prompt -> Workflow -------------------------------------------------- #
    say("[1/4] Workflow  — generating the reel …")
    result, run_dir = _step_workflow(cfg, ws, run_id)
    say(f"        stages {result.status_counts()}  ->  {run_dir}")
    if not result.ok:
        print(f"\nError: the workflow did not finish (failed stages: "
              f"{', '.join(result.failed()) or 'unknown'}).")
        return 2

    # 2) Quality ------------------------------------------------------------- #
    say("[2/4] Quality   — checking the reel …")
    report = _step_quality(result)
    counts = report.status_counts()
    say(f"        {report.overall.name}  "
        f"({counts['pass']} pass, {counts['warn']} warn, {counts['fail']} fail)")
    if not report.ok and cfg.quality_gate:
        print("\nError: the reel did not pass the quality check, so no upload "
              "metadata was written.")
        for check in report.failures:
            print(f"  - {check.label}: {check.detail}")
        print("Hint: re-run after adjusting the prompt/template, or pass "
              "--no-quality-gate to write metadata anyway.")
        return 2

    # 3) Upload Metadata ----------------------------------------------------- #
    say("[3/4] Upload    — writing upload-ready metadata …")
    metadata, files, out_dir, copied = _step_upload(cfg, result, ws, run_id)
    missing = metadata.missing_fields()
    files_ok = files.metadata_json.exists() and files.preview_md.exists()
    say(f"        {files.metadata_json.name}, {files.preview_md.name}"
        + (f", + {len(copied)} rendition(s)" if copied else ""))

    # 4) Finished ------------------------------------------------------------ #
    say("[4/4] Finished")
    say()
    print(f"Title    : {metadata.youtube_title}")
    print(f"Hashtags : {' '.join(metadata.hashtags)}")
    print(f"Exports  : {out_dir}")
    if as_json:
        print("\n" + files.metadata_json.read_text(encoding="utf-8").rstrip())

    ok = files_ok and not missing
    if not ok:
        if missing:
            print(f"\nError: some required metadata fields came out empty: "
                  f"{', '.join(missing)}.")
        if not files_ok:
            print("\nError: the upload files were not written.")
        return 2

    print(f"\n=== DONE ({cfg.renderer}) — your reel is ready to upload ===")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    configure_logging(level=logging.INFO if args.verbose else logging.WARNING)
    cfg = _resolve_config(args)
    return run(cfg, name=args.name, as_json=args.json, quiet=args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
