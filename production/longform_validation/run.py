"""Phase V2 orchestrator CLI.

    python -m production.longform_validation.run [--source DIR] [--output DIR]
        [--workspace DIR] [--baseline DIR] [--limit N] [--skip-download]
        [--skip-build] [--sample-size N] [--seed N] [--report-copy FILE]

STEP 1  download every long-form YouTube video (skip / resume / checksums)
STEP 2+3 extract audio and build the voice dataset (existing builder, reused)
STEP 4  statistics          STEP 5  random inspection
STEP 6  comparison against the raw-video baseline dataset
STEP 7  final A/B/C recommendation

Each video is staged and processed through ``voice_pipeline.glue.run_pipeline``
one at a time: a crash on a single oversized file (e.g. MemoryError while
analyzing a multi-hour WAV on an 8 GB machine) is recorded and skipped instead
of losing the whole batch, results persist incrementally via the glue's own
resume, and workspace WAVs are cleaned between files to bound disk usage.
The reused modules are never modified.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from production.media_acquisition.config import Config as MConfig
from production.media_acquisition.database import MediaDB
from production.media_acquisition.download import DownloadEngine, DownloadLog
from production.media_acquisition.manager import ProviderStats, run_provider
from production.voice_dataset.config import MEDIA_EXTS
from production.voice_pipeline.glue import run_pipeline

from .config import (DEFAULT_BASELINE, DEFAULT_OUTPUT, DEFAULT_SOURCE,
                     DEFAULT_WORKSPACE, V2Config)
from .provider import LongFormYouTubeProvider
from .stats import (dataset_metrics, dataset_stats, format_comparison,
                    format_inspection, format_recommendation, format_stats,
                    load_records, recommend, sample_inspection)
from .verify import VerifyReport, format_verify, verify_checksums


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.longform_validation.run",
        description="Validate long-form YouTube videos for production voice cloning.")
    ap.add_argument("--source", default=str(DEFAULT_SOURCE),
                    help="where long-form videos are downloaded")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT),
                    help="voice dataset output (accepted/rejected/metadata)")
    ap.add_argument("--workspace", default=str(DEFAULT_WORKSPACE),
                    help="scratch workspace for extraction (cleaned per file)")
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE),
                    help="existing raw-video dataset dir (comparison baseline)")
    ap.add_argument("--creator", default="tanshi")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap number of long-form videos (validate-first)")
    ap.add_argument("--sample-size", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--report-copy", default=None,
                    help="also write the final report to this file")
    return ap


def _banner(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}"


# --- STEP 1 --------------------------------------------------------------------

def step1_download(source: Path, limit: Optional[int],
                   provider=None) -> Tuple[ProviderStats, VerifyReport]:
    mcfg = MConfig()
    db = MediaDB(source / "media.sqlite")
    engine = DownloadEngine(mcfg, db, DownloadLog(source / "download.log"))
    prov = provider if provider is not None else LongFormYouTubeProvider(mcfg)
    stats = run_provider(prov, source, engine, mcfg, limit=limit)
    db.export_csv(source / "media.csv")
    db.export_xlsx(source / "media.xlsx")
    report = verify_checksums(db, source)
    return stats, report


def _format_download(s: ProviderStats) -> str:
    if not s.available:
        return f"  YouTube provider unavailable - {s.note}"
    return (f"  Long-form discovered : {s.discovered}\n"
            f"  Downloaded           : {s.downloaded}\n"
            f"  Skipped (already ok) : {s.skipped}\n"
            f"  Failed               : {s.failed}\n"
            f"  Hours on disk        : {s.hours:.3f}")


# --- STEPS 2+3 -------------------------------------------------------------------

def _media_files(source: Path) -> List[Path]:
    return sorted((p for p in Path(source).iterdir()
                   if p.is_file() and p.suffix.lower() in MEDIA_EXTS),
                  key=lambda p: p.name)


def _clean_dir(path: Path) -> None:
    if path.exists():
        for f in path.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)


def _stage(file: Path, stage_dir: Path) -> Path:
    stage_dir.mkdir(parents=True, exist_ok=True)
    _clean_dir(stage_dir)
    target = stage_dir / file.name
    try:
        os.link(file, target)                    # same drive: no extra disk
    except OSError:
        shutil.copyfile(file, target)
    return target


def step23_build(source: Path, workspace: Path, output: Path,
                 creator: str) -> Tuple[Optional[dict], List[str]]:
    """Run the existing builder over every video, one file per call."""
    from production.voice_dataset.config import Paths as VPaths

    stage_dir = workspace / "_stage"
    vpaths = VPaths.for_creator(workspace, creator)
    done = {r["filename"] for r in load_records(output / "metadata" / "dataset.sqlite")}
    files = _media_files(source)
    todo = [f for f in files if f.name not in done]
    print(f"  Videos found   : {len(files)}")
    print(f"  Already built  : {len(files) - len(todo)} (resume)")
    print(f"  To process     : {len(todo)}")

    summary: Optional[dict] = None
    crashed: List[str] = []
    for i, f in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {f.name}", flush=True)
        _stage(f, stage_dir)
        try:
            summary = run_pipeline(stage_dir, workspace, output,
                                   creator=creator, resume=True, progress=False)
        except Exception as e:                    # noqa: BLE001 - isolate one bad file
            crashed.append(f.name)
            print(f"      FAILED ({type(e).__name__}): {str(e)[:160]}")
        finally:
            _clean_dir(stage_dir)                 # bound disk: workspace WAVs are
            for d in (vpaths.extracted, vpaths.accepted, vpaths.rejected):
                _clean_dir(d)                     # already synced to the output dir

    if crashed:
        reports = output / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "crashed_files.json").write_text(json.dumps(crashed, indent=2))

    # spec compliance: dataset.* also visible at the output root
    meta = output / "metadata"
    for name in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        if (meta / name).exists():
            shutil.copyfile(meta / name, output / name)
    return summary, crashed


# --- orchestration ----------------------------------------------------------------

def run(argv: Optional[Sequence[str]] = None, provider=None) -> int:
    args = build_parser().parse_args(argv)
    cfg = V2Config()
    sample_size = args.sample_size if args.sample_size is not None else cfg.sample_size
    seed = args.seed if args.seed is not None else cfg.seed
    source, output = Path(args.source), Path(args.output)
    workspace, baseline = Path(args.workspace), Path(args.baseline)
    source.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    emit(_banner("STEP 1: download long-form YouTube videos"))
    if args.skip_download:
        emit("  skipped (--skip-download)")
    else:
        dstats, vreport = step1_download(source, args.limit, provider=provider)
        emit(_format_download(dstats))
        emit("  " + format_verify(vreport).replace("\n", "\n  "))

    emit(_banner("STEPS 2+3: extract audio + build voice dataset"))
    crashed: List[str] = []
    if args.skip_build:
        emit("  skipped (--skip-build)")
    else:
        _, crashed = step23_build(source, workspace, output, args.creator)
        if crashed:
            emit(f"  Crashed files (isolated, see reports/crashed_files.json): {len(crashed)}")

    records = load_records(output / "metadata" / "dataset.sqlite")
    media_db = source / "media.sqlite"
    total_videos = None
    if media_db.exists():
        total_videos = sum(1 for r in MediaDB(media_db).all()
                           if r.get("status") == "downloaded")

    emit(_banner("STEP 4: statistics — YouTube long-form dataset"))
    emit(format_stats(dataset_stats(records, total_videos=total_videos),
                      "YouTube Long-form Dataset"))

    emit(_banner("STEP 5: random inspection"))
    acc_sample, rej_sample = sample_inspection(records, sample_size, seed)
    emit(format_inspection(acc_sample, "ACCEPTED"))
    emit("")
    emit(format_inspection(rej_sample, "REJECTED"))

    emit(_banner("STEP 6: comparison — Raw Video Dataset vs YouTube Long-form"))
    base_records = load_records(baseline / "metadata" / "dataset.sqlite")
    yt_m, base_m = dataset_metrics(records), dataset_metrics(base_records)
    if not base_records:
        emit(f"  WARNING: baseline dataset not found at {baseline}")
    emit(format_comparison(yt_m, base_m, cfg))

    emit(_banner("STEP 7: final recommendation"))
    letter, reasons = recommend(yt_m, base_m, cfg)
    emit(format_recommendation(letter, reasons))

    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report_text = "\n".join(out) + "\n"
    (reports / "validation_report.txt").write_text(report_text, encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
