"""Phase V4 orchestrator CLI.

    python -m production.segment_dataset.run [--output DIR] [--workspace DIR]
        [--source kind=DIR ...] [--limit-files N] [--skip-build]
        [--sample-size N] [--seed N] [--report-copy FILE]

STEPS 1-7  segment every source recording and export accepted_segments/,
           rejected_segments/, metadata/dataset.{sqlite,csv,xlsx}
STEP 8     merged production statistics
STEP 9     seeded 50/50 inspection with programmatic verification
STEP 10    VOICE_DATASET_REPORT.md (dataset root; --report-copy for the repo)
STEP 11    sufficiency verdict + how many more minutes are needed

Resume: sources already present in metadata/dataset.sqlite are skipped, so
interrupted runs continue where they stopped. Each source file is isolated —
one bad recording cannot lose the batch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import DEFAULT_OUTPUT, DEFAULT_SOURCES, DEFAULT_WORKSPACE, V4Config
from .models import SegmentRecord
from .pipeline import discover_sources, process_source
from .report import (dataset_stats, extra_recording_estimate, format_contribution,
                     format_inspection, format_stats, readiness_estimate,
                     sample_segments, source_contribution, verify_sample)
from .storage import load_segments, row_to_record, write_all, write_sqlite


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.segment_dataset.run",
        description="Segment-level production voice dataset builder (Phase V4).")
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    ap.add_argument("--source", action="append", default=None, metavar="KIND=DIR",
                    help="override source roots (repeatable); default: all known sources")
    ap.add_argument("--limit-files", type=int, default=None,
                    help="cap number of source files (validate-first)")
    ap.add_argument("--skip-build", action="store_true",
                    help="reporting steps only, over the existing dataset")
    ap.add_argument("--sample-size", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--report-copy", default=None,
                    help="also write VOICE_DATASET_REPORT.md to this path")
    return ap


def _banner(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}"


def _parse_sources(args_source) -> Dict[str, Path]:
    if not args_source:
        return dict(DEFAULT_SOURCES)
    out: Dict[str, Path] = {}
    for spec in args_source:
        kind, _, path = spec.partition("=")
        if not path:
            raise SystemExit(f"--source expects KIND=DIR, got: {spec}")
        out[kind] = Path(path)
    return out


def build(sources: Dict[str, Path], output: Path, workspace: Path, cfg: V4Config,
          limit_files: Optional[int], emit) -> List[SegmentRecord]:
    accepted_dir = output / "accepted_segments"
    rejected_dir = output / "rejected_segments"
    metadata_dir = output / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    prior = [row_to_record(r) for r in load_segments(metadata_dir / "dataset.sqlite")]
    done = {(r.source_kind, r.source_file) for r in prior}
    # sources that produced zero segments never appear in the dataset — a
    # sidecar remembers them so resume skips them too
    processed_path = metadata_dir / "processed_sources.json"
    if processed_path.exists():
        done |= {tuple(x) for x in json.loads(processed_path.read_text())}

    files = discover_sources(sources)
    if limit_files is not None:
        files = files[:limit_files]
    todo = [(k, p, key) for k, p, key in files if (k, key) not in done]
    emit(f"  Source files found : {len(files)}")
    emit(f"  Already processed  : {len(files) - len(todo)} (resume)")
    emit(f"  To process         : {len(todo)}")

    records: List[SegmentRecord] = list(prior)
    crashed: List[str] = []
    for i, (kind, path, key) in enumerate(todo, 1):
        emit(f"  [{i}/{len(todo)}] {kind}: {key}")
        try:
            new = process_source(path, kind, key, accepted_dir, rejected_dir,
                                 workspace, cfg, next_id=len(records) + 1)
            records.extend(new)
            done.add((kind, key))
        except Exception as e:                     # noqa: BLE001 - isolate one file
            crashed.append(f"{kind}/{key}")
            emit(f"      FAILED ({type(e).__name__}): {str(e)[:160]}")
        if i % 10 == 0 or i == len(todo):          # incremental persistence
            write_sqlite(records, metadata_dir / "dataset.sqlite")
            processed_path.write_text(json.dumps(sorted(done)))

    write_all(records, metadata_dir)               # sqlite + csv + xlsx
    if crashed:
        reports = output / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "crashed_files.json").write_text(json.dumps(crashed, indent=2))
        emit(f"  Crashed files (isolated): {len(crashed)}")
    return records


def build_report_md(stats: dict, contribution: List[dict], verdict: str,
                    detail: str, extra: str, checks: dict) -> str:
    nl = "\n"
    contrib_rows = nl.join(
        f"| {r['kind']} | {r['sources']} | {r['segments']} | {r['accepted']} "
        f"| {r['accepted_minutes']:.1f} | {r['avg_snr_db']:.1f} |"
        for r in contribution) or "| (none) | | | | | |"
    reasons = nl.join(f"- {reason} ({count})"
                      for reason, count in stats["top_rejection_reasons"]) or "- none"
    noise = ", ".join(f"{k}: {v}" for k, v in
                      sorted(stats["noise_distribution"].items())) or "n/a"
    return f"""# VOICE_DATASET_REPORT — Phase V4 production dataset

## Source contribution

| source | files | segments | accepted | accepted min | avg SNR (dB) |
| --- | --- | --- | --- | --- | --- |
{contrib_rows}

## Dataset totals

- Source recordings: {stats['n_sources']}
- Segments: {stats['n_segments']} — **accepted {stats['accepted_segments']}
  ({stats['accepted_pct']:.1f}%)**, rejected {stats['rejected_segments']}
  ({stats['rejected_pct']:.1f}%)
- Accepted hours: **{stats['accepted_hours']:.3f}** (speech
  {stats['accepted_speech_hours']:.3f}); rejected hours: {stats['rejected_hours']:.3f}
- Average SNR (accepted): **{stats['avg_snr_db']:.2f} dB**
- Average loudness (accepted): {stats['avg_loudness_dbfs']:.2f} dBFS
- Average segment duration: {stats['avg_duration_s']:.1f} s
- Background noise (accepted segments): avg floor
  {stats['avg_noise_floor_dbfs']:.1f} dBFS; distribution {noise}

## Top rejection reasons

{reasons}

## Inspection verification (seeded random sample)

- Accepted sample: duration-in-band {checks['acc']['duration_in_band']},
  files exist {checks['acc']['files_exist']}, speech-ratio ok
  {checks['acc']['speech_ratio_ok']}
- Rejected sample: files exist {checks['rej']['files_exist']}

## Estimated production readiness

**{verdict}**

{detail}

{extra}
"""


def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = V4Config()
    sample_size = args.sample_size if args.sample_size is not None else cfg.sample_size
    seed = args.seed if args.seed is not None else cfg.seed
    output, workspace = Path(args.output), Path(args.workspace)
    output.mkdir(parents=True, exist_ok=True)
    sources = _parse_sources(args.source)

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    emit(_banner("STEPS 1-7: segment, evaluate, export"))
    for kind, root in sorted(sources.items()):
        note = "" if Path(root).is_dir() else "  (missing - skipped)"
        emit(f"  source {kind:<10}: {root}{note}")
    if args.skip_build:
        emit("  build skipped (--skip-build)")
    else:
        build(sources, output, workspace, cfg, args.limit_files, emit)

    rows = load_segments(output / "metadata" / "dataset.sqlite")
    n_sources = len({(r["source_kind"], r["source_file"]) for r in rows})

    emit(_banner("STEP 8: merged production dataset statistics"))
    stats = dataset_stats(rows, n_sources)
    emit(format_stats(stats))
    emit("")
    contribution = source_contribution(rows)
    emit(format_contribution(contribution))

    emit(_banner("STEP 9: random inspection"))
    acc_sample, rej_sample = sample_segments(rows, sample_size, seed)
    acc_checks = verify_sample(acc_sample, cfg)
    rej_checks = verify_sample(rej_sample, cfg)
    emit(format_inspection(acc_sample, "ACCEPTED", acc_checks))
    emit("")
    emit(format_inspection(rej_sample, "REJECTED", rej_checks))

    emit(_banner("STEPS 10+11: report + recommendation"))
    verdict, detail = readiness_estimate(stats, cfg)
    missing = max(0.0, cfg.sufficient_speech_hours - stats["accepted_hours"])
    extra = extra_recording_estimate(rows, missing)
    emit(f"  {verdict}")
    emit(f"  {detail}")
    emit(f"  {extra}")

    report_md = build_report_md(stats, contribution, verdict, detail, extra,
                                {"acc": acc_checks, "rej": rej_checks})
    (output / "VOICE_DATASET_REPORT.md").write_text(report_md, encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_md, encoding="utf-8")
    reports = output / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "run_output.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    emit(f"\n  Report: {output / 'VOICE_DATASET_REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
