"""CLI orchestration: download YouTube -> Instagram -> run Voice Dataset Builder.

Invoked by ``python -m production.media_acquisition.download``. Independent of
the voice builder except for calling its public CLI entry after downloads.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Optional, Sequence

from .config import Config, Paths
from .database import MediaDB
from .download import DownloadEngine, DownloadLog
from .manager import ProviderStats, run_provider
from .models import Platform
from .providers import InstagramProvider, YouTubeProvider


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.media_acquisition.download",
        description="Download your own YouTube + Instagram videos, then build the voice dataset.")
    ap.add_argument("--base", default=None,
                    help="production_assets base (default ./production_assets or $MEDIA_ACQ_BASE)")
    ap.add_argument("--creator", default="tanshi")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap videos per platform. Validate the pipeline with e.g. --limit 25 "
                         "before a full-channel run.")
    ap.add_argument("--youtube-only", action="store_true")
    ap.add_argument("--instagram-only", action="store_true")
    ap.add_argument("--skip-voice", action="store_true",
                    help="download only; do not run the Voice Dataset Builder")
    return ap


def _link_media_to_voice_raw(paths: Paths) -> None:
    """Expose downloaded media to the voice builder via voice/raw/{youtube,instagram}.

    Hardlink (no extra disk) with symlink/copy fallbacks.
    """
    for src, dst in ((paths.media_youtube, paths.voice_raw / "youtube"),
                     (paths.media_instagram, paths.voice_raw / "instagram")):
        dst.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            continue
        for f in sorted(src.iterdir()):
            if not f.is_file():
                continue
            target = dst / f.name
            if target.exists():
                continue
            try:
                os.link(f, target)
            except OSError:
                try:
                    os.symlink(f, target)
                except OSError:
                    shutil.copyfile(f, target)


def _run_voice_builder(base: Path, creator: str) -> None:
    from production.voice_dataset.build import main as voice_main
    voice_main(["--base", str(base), "--creator", creator])


def _voice_stats(dataset_sqlite: Path) -> Optional[dict]:
    if not Path(dataset_sqlite).exists():
        return None
    rank = {"poor": 0, "fair": 1, "good": 2, "excellent": 3}
    label = {0: "poor", 1: "fair", 2: "good", 3: "excellent"}
    conn = sqlite3.connect(str(dataset_sqlite))
    try:
        rows = conn.execute(
            "SELECT accepted, speech_duration, quality, reason FROM dataset").fetchall()
    finally:
        conn.close()
    accepted = [r for r in rows if r[0]]
    rejected = [r for r in rows if not r[0]]
    acc_hours = sum((r[1] or 0.0) for r in accepted) / 3600.0
    rej_hours = sum((r[1] or 0.0) for r in rejected) / 3600.0
    if accepted:
        avg = sum(rank.get(r[2], 0) for r in accepted) / len(accepted)
        avg_quality = label[int(round(avg))]
    else:
        avg_quality = "n/a"
    reasons: dict = {}
    for r in rejected:
        reasons[r[3]] = reasons.get(r[3], 0) + 1
    top = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {"accepted": len(accepted), "rejected": len(rejected),
            "accepted_speech_hours": round(acc_hours, 3),
            "rejected_speech_hours": round(rej_hours, 3),
            "average_quality": avg_quality, "top_rejections": top}


def _format_provider(name: str, s: ProviderStats) -> str:
    if not s.available:
        return f"\n[{name}] unavailable - {s.note}"
    return (f"\n[{name}]\n"
            f"  Videos discovered : {s.discovered}\n"
            f"  Downloaded        : {s.downloaded}\n"
            f"  Skipped           : {s.skipped}\n"
            f"  Failed            : {s.failed}\n"
            f"  Hours downloaded  : {s.hours:.3f}")


def _format_final(yt: Optional[ProviderStats], ig: Optional[ProviderStats],
                  voice: Optional[dict]) -> str:
    def media_line(s):
        if s is None:
            return "not run"
        if not s.available:
            return "unavailable (tool/credentials missing)"
        return (f"discovered {s.discovered}, downloaded {s.downloaded}, "
                f"skipped {s.skipped}, failed {s.failed}, {s.hours:.3f} h")

    total_hours = (yt.hours if yt else 0.0) + (ig.hours if ig else 0.0)
    lines = ["", "=" * 52, "  PRODUCTION SUMMARY", "=" * 52,
             f"  YouTube media   : {media_line(yt)}",
             f"  Instagram media : {media_line(ig)}",
             f"  Total downloaded: {total_hours:.3f} hours"]
    if voice is None:
        lines.append("  Voice dataset   : not built")
    else:
        lines += [
            f"  Accepted speech : {voice['accepted_speech_hours']:.3f} hours "
            f"({voice['accepted']} files)",
            f"  Rejected speech : {voice['rejected_speech_hours']:.3f} hours "
            f"({voice['rejected']} files)",
            f"  Dataset quality : {voice['average_quality']}"]
        if voice["top_rejections"]:
            lines.append("  Top rejections  :")
            for reason, count in voice["top_rejections"]:
                lines.append(f"    - {reason} ({count})")
    lines.append("=" * 52)
    return "\n".join(lines)


def run(argv: Optional[Sequence[str]] = None, providers=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config(limit=args.limit)
    base = Path(args.base) if args.base else cfg.base_dir()
    paths = Paths.for_creator(base, args.creator).ensure()

    db = MediaDB(paths.metadata / "media.sqlite")
    engine = DownloadEngine(cfg, db, DownloadLog(paths.log_file))

    if providers is None:
        providers = []
        if not args.instagram_only:
            providers.append(YouTubeProvider(cfg))
        if not args.youtube_only:
            providers.append(InstagramProvider(cfg))

    stats = {}
    for prov in providers:                       # YouTube first, then Instagram
        dest = paths.media_youtube if prov.platform == Platform.YOUTUBE else paths.media_instagram
        s = run_provider(prov, dest, engine, cfg, limit=args.limit)
        stats[prov.platform] = s
        print(_format_provider(prov.platform.value.title(), s))

    db.export_csv(paths.metadata / "media.csv")
    db.export_xlsx(paths.metadata / "media.xlsx")

    voice = None
    if not args.skip_voice:
        _link_media_to_voice_raw(paths)
        try:
            _run_voice_builder(base, args.creator)
            voice = _voice_stats(paths.metadata / "dataset.sqlite")
        except Exception as e:                    # noqa: BLE001
            print(f"\n[voice] builder step skipped/failed: {e}")

    print(_format_final(stats.get(Platform.YOUTUBE), stats.get(Platform.INSTAGRAM), voice))
    return 0
