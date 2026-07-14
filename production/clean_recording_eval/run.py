"""Phase V3 orchestrator CLI.

    python -m production.clean_recording_eval.run [--downloads DIR]
        [--recording NAME] [--raw DIR] [--output DIR] [--workspace DIR]
        [--baseline DIR] [--skip-ingest] [--skip-build] [--sample-size N]
        [--seed N] [--report-copy FILE]

STEP 1  move the recording from Downloads (verified, never overwrites)
STEP 2  run the existing Voice Dataset Builder (via the V2 per-file harness)
STEP 3  dataset statistics          STEP 4  random inspection
STEP 5  comparison vs the raw phone-recording dataset
STEP 6  Voice Cloning Readiness Score          STEP 7  A/B/C recommendation

Reuses: media_acquisition (sha256), voice_dataset (builder, thresholds
unchanged), voice_pipeline.glue (folder pipeline) and
longform_validation (per-file build harness + stats) — none of them modified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from production.longform_validation.run import step23_build
from production.longform_validation.stats import (
    QUALITY_RANK, RANK_LABEL, dataset_stats, load_records, sample_inspection)

from .config import (DEFAULT_BASELINE, DEFAULT_DOWNLOADS, DEFAULT_OUTPUT,
                     DEFAULT_RAW, DEFAULT_WORKSPACE, V3Config)
from .ingest import IngestError, find_recording, format_probe, move_verified, probe
from .score import format_readiness, readiness_score


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.clean_recording_eval.run",
        description="Evaluate a clean microphone recording as a voice-cloning dataset.")
    ap.add_argument("--downloads", default=str(DEFAULT_DOWNLOADS))
    ap.add_argument("--recording", default=None,
                    help="filename in Downloads (default: newest media file)")
    ap.add_argument("--raw", default=str(DEFAULT_RAW))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    ap.add_argument("--baseline", default=str(DEFAULT_BASELINE),
                    help="raw phone-recording dataset dir (comparison baseline)")
    ap.add_argument("--creator", default="tanshi")
    ap.add_argument("--sample-size", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--report-copy", default=None)
    return ap


def _banner(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}"


# --- STEP 3/5 metrics -------------------------------------------------------------

def eval_metrics(records: List[dict]) -> Dict[str, float]:
    accepted = [r for r in records if r["accepted"]]
    n_all, n_acc = len(records), len(accepted)
    quality = (sum(QUALITY_RANK.get(r["quality"], 0) for r in accepted) / n_acc
               if n_acc else 0.0)
    return {
        "total_clips": n_all,
        "accepted_clips": n_acc,
        "rejected_clips": n_all - n_acc,
        "acceptance_rate_pct": round(100.0 * n_acc / n_all, 1) if n_all else 0.0,
        "accepted_speech_minutes": round(sum(r["speech_duration"] for r in accepted) / 60.0, 1),
        "rejected_speech_minutes": round(sum(r["speech_duration"] for r in records
                                             if not r["accepted"]) / 60.0, 1),
        "accepted_speech_hours": round(sum(r["speech_duration"] for r in accepted) / 3600.0, 3),
        "avg_clip_duration_s": round(sum(r["duration"] for r in records) / n_all, 1)
                               if n_all else 0.0,
        "avg_snr_db": round(sum(r["snr_db"] for r in accepted) / n_acc, 2) if n_acc else 0.0,
        "avg_speech_duration_s": round(sum(r["speech_duration"] for r in accepted) / n_acc, 1)
                                 if n_acc else 0.0,
        "quality_score": round(quality, 2),
        "avg_quality_label": RANK_LABEL[int(round(quality))] if n_acc else "n/a",
    }


def format_eval_stats(records: List[dict]) -> str:
    s = dataset_stats(records)
    m = eval_metrics(records)
    lines = [f"  Total clips             : {m['total_clips']}",
             f"  Accepted clips          : {m['accepted_clips']}",
             f"  Rejected clips          : {m['rejected_clips']}",
             f"  Accepted speech minutes : {m['accepted_speech_minutes']:.1f}",
             f"  Rejected speech minutes : {m['rejected_speech_minutes']:.1f}",
             f"  Average clip duration   : {m['avg_clip_duration_s']:.1f} s",
             f"  Average SNR (accepted)  : {m['avg_snr_db']:.2f} dB",
             f"  Average quality         : {m['avg_quality_label']}"]
    if s["top_rejection_reasons"]:
        lines.append("  Top rejection reasons   :")
        for reason, count in s["top_rejection_reasons"]:
            lines.append(f"    - {reason} ({count})")
    return "\n".join(lines)


def format_inspection_snr(sample: List[dict], bucket: str) -> str:
    header = (f"  {bucket} sample ({len(sample)} clips)\n"
              f"  {'filename':<40} {'dur(s)':>8} {'quality':>9} {'SNR(dB)':>8}  reason")
    lines = [header, "  " + "-" * 104]
    for r in sample:
        lines.append(f"  {r['filename'][:40]:<40} {r['duration']:>8.1f} "
                     f"{r['quality']:>9} {r['snr_db']:>8.1f}  {r['reason']}")
    if not sample:
        lines.append("  (none)")
    return "\n".join(lines)


def format_v3_comparison(clean: Dict[str, float], base: Dict[str, float]) -> str:
    rows = [("Acceptance rate (%)", "acceptance_rate_pct", "{:.1f}"),
            ("Speech hours (accepted)", "accepted_speech_hours", "{:.3f}"),
            ("Average SNR (dB)", "avg_snr_db", "{:.2f}"),
            ("Average clip quality (0-3)", "quality_score", "{:.2f}"),
            ("Average speech duration (s)", "avg_speech_duration_s", "{:.1f}")]
    lines = [f"  {'metric':<30} {'Raw phone recordings':>22} {'Clean mic recording':>22}",
             "  " + "-" * 76]
    for label, key, fmt in rows:
        lines.append(f"  {label:<30} {fmt.format(base[key]):>22} {fmt.format(clean[key]):>22}")
    return "\n".join(lines)


# --- STEP 7 -------------------------------------------------------------------------

RECOMMENDATIONS = {
    "A": "This dataset alone is sufficient for production voice cloning.",
    "B": "Use this dataset as the primary dataset and supplement it with "
         "selected clips from the previous datasets.",
    "C": "Record additional clean speech before training.",
}


def recommend(m: Dict[str, float], overall: float, cfg: V3Config) -> tuple[str, List[str]]:
    quality_ok = (m["accepted_clips"] > 0 and m["avg_snr_db"] >= cfg.min_avg_snr_db
                  and overall >= 60.0)
    hours = m["accepted_speech_hours"]
    reasons = [
        f"Clean recording: {hours:.3f} h accepted speech "
        f"({m['accepted_speech_minutes']:.1f} min), avg SNR {m['avg_snr_db']:.1f} dB, "
        f"quality {m['avg_quality_label']}, readiness {overall:.1f}/100",
        f"Assessment bands: sufficient >= {cfg.sufficient_speech_hours:.2f} h accepted "
        f"speech, usable >= {cfg.usable_speech_hours:.2f} h, min avg SNR "
        f"{cfg.min_avg_snr_db:.0f} dB, readiness >= 60 for training use",
    ]
    if quality_ok and hours >= cfg.sufficient_speech_hours and overall >= 75.0:
        reasons.append(f"Volume ({hours:.3f} h >= {cfg.sufficient_speech_hours:.2f} h), "
                       f"quality and readiness ({overall:.1f} >= 75) all clear the bar.")
        return "A", reasons
    if quality_ok and hours >= cfg.usable_speech_hours:
        reasons.append(
            f"Quality passes but volume is below the sufficiency band "
            f"({hours:.3f} h < {cfg.sufficient_speech_hours:.2f} h); use it as the "
            f"primary source and top up with the best previous clips.")
        return "B", reasons
    reasons.append(
        "The recording does not yet provide enough usable clean speech "
        f"({hours:.3f} h accepted, readiness {overall:.1f}); more clean recording "
        "is the fastest path to a trainable dataset.")
    return "C", reasons


def format_recommendation(letter: str, reasons: List[str]) -> str:
    lines = [f"  RECOMMENDATION {letter}) {RECOMMENDATIONS[letter]}", ""]
    lines += [f"  - {r}" for r in reasons]
    return "\n".join(lines)


# --- orchestration --------------------------------------------------------------------

def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = V3Config()
    sample_size = args.sample_size if args.sample_size is not None else cfg.sample_size
    seed = args.seed if args.seed is not None else cfg.seed
    raw, output = Path(args.raw), Path(args.output)
    raw.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    emit(_banner("STEP 1: move + verify the clean recording"))
    if args.skip_ingest:
        emit("  ingest skipped (--skip-ingest); using files already in raw/")
    else:
        try:
            src = find_recording(Path(args.downloads), name=args.recording)
            dest, checksum = move_verified(src, raw)
            emit(f"  Moved {src} -> {dest}")
            emit(format_probe(probe(dest), checksum))
        except IngestError as e:
            emit(f"  Ingest: {e}")
            existing = sorted(p.name for p in raw.iterdir() if p.is_file())
            if not existing:
                emit("  No recording available - aborting.")
                return 1
            emit(f"  Continuing with existing raw files: {', '.join(existing)}")

    emit(_banner("STEP 2: run the existing Voice Dataset Builder"))
    if args.skip_build:
        emit("  skipped (--skip-build)")
    else:
        _, crashed = step23_build(raw, Path(args.workspace), output, args.creator)
        if crashed:
            emit(f"  Crashed files (isolated): {len(crashed)}")

    records = load_records(output / "metadata" / "dataset.sqlite")

    emit(_banner("STEP 3: dataset statistics — clean mic recording"))
    emit(format_eval_stats(records))

    emit(_banner("STEP 4: random inspection"))
    acc_sample, rej_sample = sample_inspection(records, sample_size, seed)
    emit(format_inspection_snr(acc_sample, "ACCEPTED"))
    emit("")
    emit(format_inspection_snr(rej_sample, "REJECTED"))

    emit(_banner("STEP 5: comparison — raw phone recordings vs clean mic recording"))
    base_records = load_records(Path(args.baseline) / "metadata" / "dataset.sqlite")
    if not base_records:
        emit(f"  WARNING: baseline dataset not found at {args.baseline}")
    clean_m, base_m = eval_metrics(records), eval_metrics(base_records)
    emit(format_v3_comparison(clean_m, base_m))

    emit(_banner("STEP 6: Voice Cloning Readiness Score"))
    score = readiness_score(records, cfg)
    emit(format_readiness(score))

    emit(_banner("STEP 7: final recommendation"))
    letter, reasons = recommend(clean_m, score.overall, cfg)
    emit(format_recommendation(letter, reasons))

    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    report_text = "\n".join(out) + "\n"
    (reports / "evaluation_report.txt").write_text(report_text, encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
