"""Phase V4.1 orchestrator CLI — incremental production dataset expansion.

    python -m production.segment_dataset.expansion [--downloads DIR]
        [--zips DIR] [--extracted DIR] [--new-output DIR] [--prod DIR]
        [--workspace DIR] [--skip-ingest] [--skip-build] [--skip-merge]
        [--sample-size N] [--seed N] [--report-copy FILE]

STEP 1  locate New_videos_for_voice_clone*.zip in Downloads
STEP 2  verified move to zips/ (never overwrites)
STEP 3  resumable extraction to extracted/
STEP 4  media scan (count / duration / storage / formats)
STEP 5  the EXISTING Phase V4 builder over the new videos only
STEP 6  SHA256-deduped merge of accepted segments into production
STEP 7  old / new / merged comparison
STEP 8  seeded 30/30 audit of the new run
STEP 9  final merged production summary + validation checklist

Purely additive: Phase V4 modules are called, never modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional, Sequence

from .config import DEFAULT_OUTPUT, V4Config
from .expand import extract_zips, find_zips, format_scan, move_zips, scan_media
from .merge import comparison, format_validation, merge_accepted, validate_merge
from .report import (dataset_stats, format_inspection, format_stats,
                     readiness_estimate, sample_segments, verify_sample)
from .run import run as v4_run
from .storage import load_segments

DEFAULT_DOWNLOADS = Path.home() / "Downloads"
DEFAULT_BASE = Path(r"D:\AI_CREATOR_DATA\Tanshi\new_raw_videos")
DEFAULT_NEW_OUTPUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\new_voice_dataset")
DEFAULT_NEW_WORKSPACE = Path(r"D:\AI_CREATOR_DATA\Tanshi\_workspace_expansion")
NEW_KIND = "new_raw"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.segment_dataset.expansion",
        description="Incremental expansion of the V4 production voice dataset.")
    ap.add_argument("--downloads", default=str(DEFAULT_DOWNLOADS))
    ap.add_argument("--zips", default=str(DEFAULT_BASE / "zips"))
    ap.add_argument("--extracted", default=str(DEFAULT_BASE / "extracted"))
    ap.add_argument("--new-output", default=str(DEFAULT_NEW_OUTPUT))
    ap.add_argument("--prod", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--workspace", default=str(DEFAULT_NEW_WORKSPACE))
    ap.add_argument("--skip-ingest", action="store_true",
                    help="skip STEPS 1-3 (ZIPs already moved and extracted)")
    ap.add_argument("--skip-build", action="store_true",
                    help="skip STEP 5 (new dataset already built)")
    ap.add_argument("--skip-merge", action="store_true",
                    help="skip STEP 6 (report/audit only)")
    ap.add_argument("--sample-size", type=int, default=30)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--report-copy", default=None)
    return ap


def _banner(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}"


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = V4Config()
    seed = args.seed if args.seed is not None else cfg.seed
    zips_dir, extracted = Path(args.zips), Path(args.extracted)
    new_out, prod = Path(args.new_output), Path(args.prod)

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    if args.skip_ingest:
        emit(_banner("STEPS 1-3: skipped (--skip-ingest)"))
    else:
        emit(_banner("STEP 1: locate new ZIPs"))
        zips = find_zips(Path(args.downloads))
        total_gb = sum(z.stat().st_size for z in zips) / 1e9
        emit(f"  ZIP count : {len(zips)}")
        emit(f"  Total size: {total_gb:.2f} GB")
        for z in zips:
            emit(f"    - {z.name} ({z.stat().st_size / 1e9:.2f} GB)")

        emit(_banner("STEP 2: verified move to zips/"))
        moved, notes = move_zips(zips, zips_dir)
        emit(f"  In place at {zips_dir}: {len(moved)}")
        for n in notes:
            emit(f"    note: {n}")

        emit(_banner("STEP 3: extraction (resumable)"))
        done, skipped = extract_zips(zips_dir, extracted)
        emit(f"  Extracted now      : {len(done)} ({', '.join(done) if done else '-'})")
        emit(f"  Already extracted  : {len(skipped)}")

    emit(_banner("STEP 4: scan extracted media"))
    scan = scan_media(extracted)
    emit(format_scan(scan))
    if scan.files == 0 and not args.skip_build:
        emit("  No new media found - aborting.")
        return 1

    emit(_banner("STEP 5: EXISTING V4 builder over the new videos only"))
    if args.skip_build:
        emit("  skipped (--skip-build)")
    else:
        rc = v4_run(["--source", f"{NEW_KIND}={extracted}",
                     "--output", str(new_out), "--workspace", str(args.workspace),
                     "--sample-size", "0", "--seed", str(seed)])
        if rc != 0:
            emit(f"  V4 builder returned {rc} - aborting before merge.")
            return rc

    new_rows = load_segments(new_out / "metadata" / "dataset.sqlite")
    old_rows = load_segments(prod / "metadata" / "dataset.sqlite")

    emit(_banner("STEP 6: SHA256-deduped merge of accepted segments"))
    if args.skip_merge:
        emit("  skipped (--skip-merge)")
        stats = {"added": 0, "duplicates_skipped": 0, "missing_files": [],
                 "old_rows": len(old_rows), "merged_rows": len(old_rows)}
    else:
        stats = merge_accepted(new_out, prod)
        emit(f"  New accepted segments : {stats['new_accepted']}")
        emit(f"  Added to production   : {stats['added']}")
        emit(f"  Duplicates skipped    : {stats['duplicates_skipped']}")
        if stats["missing_files"]:
            emit(f"  Missing WAVs          : {len(stats['missing_files'])}")

    merged_rows = load_segments(prod / "metadata" / "dataset.sqlite")

    emit(_banner("STEP 7: comparison — old vs new vs merged"))
    _, comp_text = comparison(old_rows, new_rows, merged_rows)
    emit(comp_text)

    emit(_banner("STEP 8: random audit of the new run (seeded)"))
    acc_sample, rej_sample = sample_segments(new_rows, args.sample_size, seed)
    acc_checks = verify_sample(acc_sample, cfg)
    rej_checks = verify_sample(rej_sample, cfg)
    emit(format_inspection(acc_sample, "NEWLY ACCEPTED", acc_checks))
    emit("")
    emit(format_inspection(rej_sample, "NEWLY REJECTED", rej_checks))
    def _frac_ok(v: str) -> bool:
        return v == "n/a" or v.split("/")[0] == v.split("/")[1]

    audit_ok = all(_frac_ok(acc_checks[k]) for k in
                   ("duration_in_band", "files_exist", "speech_ratio_ok")) \
        and _frac_ok(rej_checks["files_exist"])

    emit(_banner("STEP 9: final merged production summary"))
    n_sources = len({(r["source_kind"], r["source_file"]) for r in merged_rows})
    final = dataset_stats(merged_rows, n_sources)
    old_h = sum(r["duration"] for r in old_rows if r["accepted"]) / 3600.0
    emit(f"  {old_h:.3f} h existing + "
         f"{final['accepted_hours'] - old_h:+.3f} h new = "
         f"{final['accepted_hours']:.3f} h final production dataset")
    emit("")
    emit(format_stats(final))
    verdict, detail = readiness_estimate(final, cfg)
    emit(f"\n  {verdict}")
    emit(f"  {detail}")

    emit(_banner("VALIDATION"))
    checks = validate_merge(prod, old_rows, stats["added"], audit_ok)
    emit(format_validation(checks))

    report_text = "\n".join(out) + "\n"
    reports = new_out / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "expansion_report.txt").write_text(report_text, encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_text, encoding="utf-8")
    return 0 if all(checks.values()) else 2


if __name__ == "__main__":
    raise SystemExit(run())
