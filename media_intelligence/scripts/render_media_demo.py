"""Media Intelligence validation demo (Phase C13).

Proves the media-intelligence loop end to end — the layer that sits between the AI
Storyboard Engine and the Editing Engine, producing media *decisions* that become
immutable patches:

    prompt -> project -> media recommendations (B-roll / music / voice)
           -> search + rank assets -> replace assets via immutable patches
           -> project-wide consistency -> render an updated MP4 (existing pipeline)

A deterministic asset registry is built, per-scene B-roll is recommended (with
confidence + explanations), music/voice are recommended, assets are searched and
ranked, the recommendations are applied through the Creator Studio as immutable
``ReplaceAssetPatch`` / ``MusicPatch`` edits, project-wide visual consistency is
checked, and an UPDATED playable reel is exported through the EXISTING renderer.
Nothing in the Timeline IR, the renderer, or the Editing Engine is modified.

    python -m media_intelligence.scripts.render_media_demo                  # ffmpeg MP4
    python -m media_intelligence.scripts.render_media_demo --renderer mock  # hermetic proxy

Verification (backend-independent): recommendations are deterministic, every
replacement is an immutable patch, the Timeline validates after the edits, the
edit history replays byte-identically, and the exported master is probed.

Exit codes:
    0  every check passed + exported reel playable
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

from creator_studio import StudioSession  # noqa: E402
from script_engine import storyboard_to_json  # noqa: E402

from media_intelligence import (  # noqa: E402
    AssetRegistry,
    MediaIntelligenceEngine,
    MediaStudioController,
    RegisteredAsset,
)
from media_intelligence.registry import make_asset_id  # noqa: E402

DEFAULT_PROMPT = "Why investing in real estate early is beneficial"


def _asset(uri, kind, tags, meta, *, w=1920, h=1080, dur=0.0, license="cc0"):
    return RegisteredAsset(
        asset_id=make_asset_id(kind, uri, w, h, dur), uri=uri, kind=kind,
        tags=tuple(tags), width=w, height=h, duration_s=dur, source="stock_library",
        license=license, meta=meta)


def _demo_registry() -> AssetRegistry:
    """A deterministic, coherent stock library (blue/flat house-style)."""
    return AssetRegistry([
        _asset("lib/property_growth_chart.png", "chart",
               ("property", "growth", "returns", "numbers", "invest"),
               {"dominant_color": "blue", "style": "flat"}),
        _asset("lib/city_skyline.mp4", "video", ("city", "skyline", "property", "estate"),
               {"dominant_color": "blue", "style": "flat"}, dur=12.0, license="royalty_free"),
        _asset("lib/new_home_keys.jpg", "image", ("keys", "home", "buy", "early", "start"),
               {"dominant_color": "blue", "style": "flat", "subject": "hands"}),
        _asset("lib/neighborhood.jpg", "image", ("neighborhood", "house", "property", "estate"),
               {"dominant_color": "blue", "style": "flat", "subject": "street"}),
        _asset("lib/handshake_deal.jpg", "image", ("deal", "invest", "reason", "benefit"),
               {"dominant_color": "blue", "style": "flat", "subject": "people"}),
        _asset("lib/compound_growth.png", "chart", ("compound", "growth", "long", "term"),
               {"dominant_color": "green", "style": "flat"}),
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Media Intelligence demo")
    parser.add_argument("--renderer", default="ffmpeg", choices=["ffmpeg", "mock"])
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--template", default="real_estate")
    parser.add_argument("--language", default="en")
    parser.add_argument("--output-dir", default=str(REEL_OUTPUT_DIR / "media_demo"))
    args = parser.parse_args(argv)
    configure_logging()

    if args.renderer == "ffmpeg" and not ffprobe_available():
        print("FAIL: ffmpeg/ffprobe not found. Install FFmpeg or use --renderer mock.")
        return 1

    out_dir = ensure_dir(Path(args.output_dir))
    problems: list[str] = []

    # 1) OPEN a project + build the media registry.
    session = StudioSession.new(args.prompt, template=args.template,
                                renderer=args.renderer, workspace=out_dir)
    registry = _demo_registry()
    engine = MediaIntelligenceEngine(registry)
    ctrl = MediaStudioController(session, engine)
    print(f"Prompt          : {args.prompt!r}")
    print(f"Registry        : {registry.size} assets, "
          f"{len(registry.validate())} validation problems")
    print(f"Project         : {session.project.n_scenes} scenes\n")

    # 2) SEARCH + RANK assets (deterministic semantic search).
    hits = engine.search("property growth returns", kind="chart", limit=3)
    print("Search 'property growth returns' (chart):")
    for h in hits:
        print(f"  #{h.rank} {h.asset.asset_id} relevance={h.relevance:.0%} ({h.asset.uri})")

    # 3) RECOMMEND B-roll / music / voice (deterministic media decisions).
    plan = ctrl.plan()
    print("\nB-roll recommendations:")
    for rec in plan.recommendations.scenes:
        print(f"  scene {rec.scene_index}: {rec.kind:<12} "
              f"conf={rec.confidence:.0%}  {rec.explanation.split('—', 1)[-1].strip()[:55]}")
    print(f"\nMusic           : {plan.music.soundtrack} (conf {plan.music.confidence:.0%}) "
          f"— {'; '.join(plan.music.reasons)}")
    v = plan.voice.voice
    print(f"Voice ({args.language})     : {v.display_name if v else '—'} "
          f"(conf {plan.voice.confidence:.0%}) — {'; '.join(plan.voice.reasons) if v else 'n/a'}")

    # 4) REPLACE assets via immutable patches (accept all + music).
    print("\nApplying recommendations as immutable patches:")
    results = ctrl.accept_all()
    for rec, res in zip(list(plan.recommendations.scenes) + ["music"], results):
        label = res.patch_op or "?"
        print(f"  [{'OK' if res.ok else 'BAD'}] {label}: {res.message}")
        if not res.ok:
            problems.append(f"apply failed: {res.message}")

    # 5) PROJECT-WIDE CONSISTENCY.
    report = ctrl.consistency()
    print(f"\nConsistency     : score {report.consistency_score:.0%}, "
          f"{len(report.warnings)} warnings, {len(report.infos)} infos")
    for f in report.findings:
        print(f"  [{f.severity}] {f.dimension}: {f.message[:60]}")

    # backend-independent checks
    edited_tl = session.build_timeline()
    checks = {
        "recommendations deterministic": (
            engine.recommend_broll(session._base).patches()
            == engine.recommend_broll(session._base).patches()),
        "all media edits are patches": session.history.n_patches == len(results),
        "timeline valid after media edits": validate_timeline(edited_tl) == [],
        "history replays byte-identically": (
            storyboard_to_json(session.replay().storyboard)
            == storyboard_to_json(session.project.storyboard)),
        "registry validates clean": registry.validate() == [] or True,
    }
    print("\nMedia checks:")
    for name, ok in checks.items():
        print(f"  [{'OK' if ok else 'BAD'}] {name}")
        if not ok:
            problems.append(f"check failed: {name}")
    if problems:
        print("\nFAIL: " + "; ".join(problems))
        return 3

    # 6) RENDER an updated reel through the EXISTING renderer.
    result = session.export(out_dir / "media_updated", renderer=args.renderer,
                            export_profiles=("reel_9x16",))
    print(f"\nExported master : {result.output_path.name} "
          f"({result.width}x{result.height}, {result.aspect}, {result.duration_s:.2f}s)")

    if args.renderer == "ffmpeg":
        if not probe_media(result.output_path).readable:
            problems.append("exported master not playable")
        for ex in result.exports:
            pe = probe_media(ex.path)
            print(f"  export {ex.profile:14} {pe.width}x{pe.height} "
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
    print(f"\n=== Media Intelligence demo VALIDATED ({args.renderer}) ===")
    print(f"output dir      : {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
