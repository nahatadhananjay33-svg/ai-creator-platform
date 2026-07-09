"""Creator Studio validation demo (Phase C12).

Drives the deterministic Creator Studio through the whole stop condition — the
same interface a graphical front-end would render, printed as a textual "screen":

    open ─► storyboard/timeline ─► review ─► edit (immutable patches)
         ─► incremental regeneration ─► preview ─► export (updated reel)

A project is opened, its scenes + timeline are shown, a review runs, a set of
immutable patches is applied through the Editing Engine (the Studio never mutates
the project), the incremental-render plan is printed (reused vs regenerated
scenes + cache statistics), the current project is previewed, and an UPDATED reel
is exported through the EXISTING renderer. Nothing in the Timeline IR or the
renderer is modified — the Studio is an interface layer over immutable patches.

    python -m creator_studio.scripts.render_studio_demo                  # ffmpeg MP4
    python -m creator_studio.scripts.render_studio_demo --renderer mock  # hermetic proxy

Verification (backend-independent): the Timeline validates after every patch, the
edit history replays byte-identically (deterministic), the incremental plan
reports genuine scene reuse, a save/open round-trip preserves the project, and the
preview + exported masters are probed for playability.

Exit codes:
    0  every check passed + preview/export playable
    1  ffmpeg unavailable for the ffmpeg renderer
    3  a validation check or an output failed
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import REEL_OUTPUT_DIR, ensure_dir  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402

from reel_engine.render import ffprobe_available, probe_media  # noqa: E402
from reel_engine.timeline.validate import validate_timeline  # noqa: E402

from script_engine import storyboard_to_json  # noqa: E402

from creator_studio import StudioSession, load_project  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"
#: Apostrophe-free narration keeps ffmpeg drawtext captions happy (matches the
#: Editing Engine demo). A representative patch set spanning content, structure,
#: presentation, and AI regeneration — every one an immutable Patch.
_EDITS = [
    ("set_narration", dict(index=1, narration="Here is the single biggest reason to start early.")),
    ("move_scene", dict(from_index=2, to_index=4)),
    ("insert_scene", dict(index=3, narration="Picture the compounding growth over the next ten years.")),
    ("delete_scene", dict(index=5)),
    ("set_duration", dict(index=1, duration_s=6.0)),
    ("set_theme", dict(theme="finance")),
    ("set_music", dict(soundtrack="cinematic")),
    ("set_caption", dict(preset="tiktok")),
    ("regenerate_scene", dict(index=2, instruction="Explain the long term returns of property")),
]


def _print_storyboard(session: StudioSession) -> None:
    panel = session.view().storyboard
    print(f"Storyboard      : {panel.n_scenes} scenes (selected {panel.selected_index})")
    for row in panel.scenes:
        mark = "►" if row.selected else " "
        print(f"  {mark} [{row.index}] {row.scene_type:<14} {row.preview}")


def _print_timeline(session: StudioSession) -> None:
    panel = session.view().timeline
    print(f"Timeline        : {panel.total_duration_s:.1f}s  {panel.width}x{panel.height} "
          f"({panel.aspect})  playhead={panel.playhead_s:.1f}s")
    for bar in panel.bars:
        tag = {"reused": "reuse", "changed": "REGEN", "base": "     "}[bar.status]
        print(f"  [{bar.index}] {bar.start_s:6.1f}–{bar.end_s:6.1f}s  {tag}  {bar.scene_id}")


def _print_incremental(session: StudioSession) -> None:
    inc = session.view().incremental
    print(f"Incremental     : {inc.n_changed}/{inc.total} scenes changed, "
          f"{inc.n_reused} reused ({inc.reuse_fraction:.0%}), overlays_changed={inc.overlays_changed}")
    print(f"  cache stats   : hits={inc.cache_hits} misses={inc.cache_misses} "
          f"cacheable={inc.cacheable_hits}  needs_render={inc.needs_render}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Creator Studio demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "studio_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    problems: list[str] = []

    # 1) OPEN a project (prompt -> editable ReelProject) into a Studio session.
    session = StudioSession.new(
        args.prompt, template=args.template, renderer=args.renderer, workspace=out_dir)
    print(f"Prompt          : {args.prompt!r}")
    print(f"Opened project  : {session.project.n_scenes} scenes, "
          f"theme={session.project.theme} music={session.project.soundtrack}\n")

    # 2) DISPLAY scenes + timeline (the Studio's read-only panels).
    _print_storyboard(session)
    _print_timeline(session)

    # 3) REVIEW (deterministic human-in-the-loop inspection).
    report = session.review()
    print(f"\nReview          : {len(report.findings)} findings ({len(report.warnings)} warnings)")

    # 4) EDIT: apply the patch set through the engine, validating after each.
    print("Applying edits (Timeline validated after each, all immutable patches):")
    for name, kwargs in _EDITS:
        result = getattr(session, name)(**kwargs)
        valid = validate_timeline(session.build_timeline()) == []
        flag = "OK" if (result.ok and valid) else "BAD"
        print(f"  [{flag}] {result.patch_op or name}: {result.message}")
        if not result.ok:
            problems.append(f"edit {name} rejected: {result.problems}")
        if not valid:
            problems.append(f"invalid timeline after {name}")

    # 5) INCREMENTAL REGENERATION (reused vs regenerated scenes + cache stats).
    print()
    _print_incremental(session)
    _print_timeline(session)

    # backend-independent checks
    save_path = out_dir / "project.studio.json"
    session.save(save_path)
    reopened = load_project(save_path)
    checks = {
        "timeline valid after every patch": not problems,
        "history replays byte-identically (deterministic)": (
            storyboard_to_json(session.replay().storyboard)
            == storyboard_to_json(session.project.storyboard)),
        "edited timeline validates": validate_timeline(session.build_timeline()) == [],
        "incremental plan reuses scenes": session.view().incremental.n_reused >= 1,
        "save/open round-trip preserves project": (
            reopened.revision == session.revision and reopened.theme == session.project.theme),
        "edits applied (revision advanced)": session.revision == len(_EDITS),
    }
    print("\nStudio checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"check failed: {name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    # 6) PREVIEW + EXPORT the updated reel through the EXISTING renderer.
    preview = session.preview()
    print(f"\nPreview         : {Path(preview['media_path']).name}")
    result = session.export(out_dir / "updated_reel", renderer=args.renderer,
                            export_profiles=("reel_9x16", "square_1x1"))
    print(f"Exported master : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    if args.renderer == "ffmpeg":
        for label, path in [("preview", Path(preview["media_path"])),
                            ("master", result.output_path)]:
            if not probe_media(path).readable:
                problems.append(f"{label} not playable")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} {ex.aspect} "
                  f"{pe.duration_s:.2f}s  {'OK' if pe.readable else 'BAD'}")
            if not pe.readable:
                problems.append(f"export {ex.profile} not playable")
    else:
        from foundation.shared_utils.video_io import read_raw_avi
        if read_raw_avi(result.output_path).n_frames <= 0:
            problems.append("mock export has no frames")

    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3
    print(f"\n=== Creator Studio demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
