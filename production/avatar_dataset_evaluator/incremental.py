"""Phase A1 — incremental evaluation of NEW videos against the A0 dataset.

    python -m production.avatar_dataset_evaluator.incremental

Evaluates ONLY the newly extracted videos (default
``D:\\AI_CREATOR_DATA\\Tanshi\\new_raw_videos\\extracted``) with the UNMODIFIED
A0 evaluator, writes a separate ``avatar_dataset_new`` tree (the production
avatar dataset is never touched, nothing is merged), measures the 12 required
viewpoint categories, compares old vs new, answers the 14 phase questions,
audits 30/30 clips, and prints READY TO MERGE or NEEDS MORE RECORDING.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .config import Config
from .coverage import (CATEGORY_LABELS, CoverageConfig, analyze_coverage,
                       coverage_minutes, format_coverage)
from .models import Record
from .pipeline import evaluate_dataset
from .report import build_report, format_report
from .storage import load_records, write_csv, write_sqlite, write_xlsx

NEW_SOURCE = Path(r"D:\AI_CREATOR_DATA\Tanshi\new_raw_videos\extracted")
NEW_OUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_new")
OLD_OUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset")

# categories the phase explicitly asks about "recovering"
RECOVERY_CATS = ["left_20", "right_20", "looking_up", "looking_down",
                 "smiling", "serious"]
MODEL_ENOUGH_PCT = 70


@dataclass(frozen=True)
class NewPaths:
    """Same shape as config.Paths, pointed at the A1 source/output."""
    source: Path
    out: Path

    @property
    def accepted(self) -> Path: return self.out / "accepted"
    @property
    def rejected(self) -> Path: return self.out / "rejected"
    @property
    def reports(self) -> Path: return self.out / "reports"
    @property
    def thumbnails(self) -> Path: return self.out / "thumbnails"

    def ensure(self) -> "NewPaths":
        for p in (self.accepted, self.rejected, self.reports, self.thumbnails):
            p.mkdir(parents=True, exist_ok=True)
        return self


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m production.avatar_dataset_evaluator.incremental",
        description="Phase A1: evaluate new videos only; no merge.")
    ap.add_argument("--source", default=str(NEW_SOURCE))
    ap.add_argument("--out", default=str(NEW_OUT))
    ap.add_argument("--old", default=str(OLD_OUT))
    ap.add_argument("--skip-eval", action="store_true",
                    help="reuse the existing avatar_dataset_new dataset")
    ap.add_argument("--sample-n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260715)
    ap.add_argument("--report-copy", default=None)
    return ap


def _banner(title: str) -> str:
    return f"\n{'=' * 64}\n  {title}\n{'=' * 64}"


# --- comparison ------------------------------------------------------------------

def _cmp_metrics(rep: dict) -> Dict[str, str]:
    d = rep["diversity"]
    return {
        "Accepted clips": f"{rep['accepted']}",
        "Accepted minutes": f"{rep['usable_hours'] * 60:.1f}",
        "Face visibility (avg %)": f"{rep['avg_face_visibility']:.1f}",
        "Lighting (avg /255)": f"{rep['avg_lighting']:.0f}",
        "Stability (avg 0-1)": f"{rep['avg_stability']:.2f}",
        "Pose F/L/R": f"{d['front_facing']}/{d['left_profile']}/{d['right_profile']}",
        "Expressions smile/neutral/talk":
            f"{d['smiling']}/{d['neutral']}/{d['talking']}",
        "Angles frontal vs profile":
            f"{d['front_facing']} vs {d['left_profile'] + d['right_profile']}",
        "Movement standing/walking": f"{d['standing']}/{d['walking']}",
    }


def format_comparison(old_rep: dict, new_rep: dict) -> str:
    old_m, new_m = _cmp_metrics(old_rep), _cmp_metrics(new_rep)
    lines = [f"  {'metric':<32} {'Old (A0)':>16} {'New (A1)':>16}",
             "  " + "-" * 66]
    for k in old_m:
        lines.append(f"  {k:<32} {old_m[k]:>16} {new_m[k]:>16}")
    return "\n".join(lines)


# --- the 14 questions ----------------------------------------------------------------

def _recovered(cov_min: Dict[str, dict], cat: str, ccfg: CoverageConfig) -> str:
    v = cov_min[cat]
    if v["minutes"] >= ccfg.min_category_minutes:
        return f"YES - {v['clips']} clips, {v['minutes']:.1f} min"
    if v["minutes"] > 0:
        return f"PARTIAL - {v['clips']} clips, only {v['minutes']:.1f} min"
    return "NO - not present in the new footage"


def answer_questions(old_rep: dict, new_rep: dict, merged_rep: dict,
                     cov_min: Dict[str, dict], verdict_ready: bool,
                     ccfg: CoverageConfig) -> List[Tuple[str, str]]:
    new_min = new_rep["usable_hours"] * 60
    improves = (merged_rep["readiness"] >= old_rep["readiness"]
                and new_rep["accepted"] > 0)
    gains = [CATEGORY_LABELS[c] for c in RECOVERY_CATS
             if cov_min[c]["minutes"] >= ccfg.min_category_minutes]
    qa = [
        ("1. Does the new dataset improve avatar quality?",
         (f"YES - +{new_rep['accepted']} accepted clips (+{new_min:.1f} min), "
          f"readiness {old_rep['readiness']} -> {merged_rep['readiness']}, "
          f"adds: {', '.join(gains) if gains else 'volume only'}")
         if improves else
         (f"NO - readiness would move {old_rep['readiness']} -> "
          f"{merged_rep['readiness']} and the new footage adds no missing view")),
        ("2. Did we recover Left views?", _recovered(cov_min, "left_20", ccfg)),
        ("3. Did we recover Right views?", _recovered(cov_min, "right_20", ccfg)),
        ("4. Did we recover Looking Up?", _recovered(cov_min, "looking_up", ccfg)),
        ("5. Did we recover Looking Down?", _recovered(cov_min, "looking_down", ccfg)),
        ("6. Did we recover Smiling?", _recovered(cov_min, "smiling", ccfg)),
        ("7. Did we recover Serious?", _recovered(cov_min, "serious", ccfg)),
    ]
    for i, model in enumerate(("MuseTalk", "LatentSync", "Hallo2", "EchoMimic"), start=8):
        merged_pct = merged_rep["models"][model]
        new_pct = new_rep["models"][model]
        enough = merged_pct >= MODEL_ENOUGH_PCT
        qa.append((f"{i}. Are there enough clips for {model}?",
                   f"{'YES' if enough else 'NOT YET'} - merged feasibility "
                   f"{merged_pct}% (new footage alone: {new_pct}%)"))
    qa += [
        ("12. Should these videos be merged into the production avatar dataset?",
         ("YES - quality holds and coverage/volume increase (see verdict)"
          if verdict_ready else "NO - see verdict for what is missing")),
        ("13. If merged, what will be the new Avatar Readiness Score?",
         f"{merged_rep['readiness']}/100 (currently {old_rep['readiness']}/100)"),
        ("14. What still remains missing?",
         "; ".join(merged_rep["missing"]
                   + [f"{CATEGORY_LABELS[c]} coverage < {ccfg.min_category_minutes:.0f} min"
                      for c in RECOVERY_CATS
                      if cov_min[c]["minutes"] < ccfg.min_category_minutes])
         or "nothing - dataset is well rounded"),
    ]
    return qa


# --- audit -------------------------------------------------------------------------

def audit(records: List[Record], n: int, seed: int, cfg: Config) -> Tuple[str, bool]:
    rng = random.Random(seed)
    acc = [r for r in records if r.accepted]
    rej = [r for r in records if not r.accepted]
    acc_s = rng.sample(acc, min(n, len(acc)))
    rej_s = rng.sample(rej, min(n, len(rej)))

    def _ok(r: Record) -> bool:
        return (r.face_visibility_pct >= cfg.no_face_below_pct
                and r.motion_blur >= cfg.heavy_blur_below
                and r.camera_stability >= cfg.too_shaky_below
                and cfg.very_dark_below < r.lighting_mean < cfg.very_bright_above)

    acc_pass = sum(1 for r in acc_s if _ok(r))
    rej_pass = sum(1 for r in rej_s if r.reject_reason)
    lines = [f"  ACCEPTED sample ({len(acc_s)}): {acc_pass}/{len(acc_s)} pass "
             f"face/blur/stability/lighting gates",
             f"  {'file':<38} {'face%':>6} {'light':>6} {'stab':>5} {'blur':>7} "
             f"{'pose':<13} expression"]
    for r in acc_s[:60]:
        lines.append(f"  {r.filename[:38]:<38} {r.face_visibility_pct:>6.0f} "
                     f"{r.lighting_mean:>6.0f} {r.camera_stability:>5.2f} "
                     f"{r.motion_blur:>7.0f} {r.face_view:<13} {r.expression}")
    lines.append("")
    lines.append(f"  REJECTED sample ({len(rej_s)}): {rej_pass}/{len(rej_s)} "
                 f"have an explicit reject reason")
    for r in rej_s[:60]:
        lines.append(f"  {r.filename[:38]:<38} {r.reject_reason[:64]}")
    ok = acc_pass == len(acc_s) and rej_pass == len(rej_s)
    return "\n".join(lines), ok


# --- orchestration --------------------------------------------------------------------

def run(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cfg, ccfg = Config(), CoverageConfig()
    paths = NewPaths(source=Path(args.source), out=Path(args.out)).ensure()

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    emit(_banner("A1: evaluate NEW videos with the unmodified A0 evaluator"))
    emit(f"  Source: {paths.source}")
    if args.skip_eval:
        records = load_records(paths.out / "dataset.sqlite")
        emit(f"  (--skip-eval: loaded {len(records)} existing records)")
    else:
        if not paths.source.exists():
            emit(f"  Source folder not found: {paths.source}")
            return 1
        records = evaluate_dataset(paths, cfg, resume=True, progress=True)
        write_sqlite(records, paths.out / "dataset.sqlite")
        write_csv(records, paths.out / "dataset.csv")
        write_xlsx(records, paths.out / "dataset.xlsx")
    if not records:
        emit("  No new videos found - nothing to evaluate.")
        return 1

    new_rep = build_report(records)
    emit(format_report(new_rep))

    emit(_banner("Viewpoint coverage of the new accepted clips"))
    covs = {}
    accepted = [r for r in records if r.accepted]
    for i, r in enumerate(accepted, 1):
        src = paths.accepted / r.filename
        if src.exists():
            covs[r.filename] = analyze_coverage(src, ccfg)
        if i % 25 == 0:
            emit(f"  ... coverage {i}/{len(accepted)}")
    cov_min = coverage_minutes(records, covs, ccfg)
    emit(format_coverage(cov_min, ccfg))

    emit(_banner("Comparison: Old Avatar Dataset (A0) vs New Dataset"))
    old_records = load_records(Path(args.old) / "dataset.sqlite")
    if not old_records:
        emit(f"  WARNING: old dataset not found at {args.old}")
    old_rep = build_report(old_records)
    merged_rep = build_report(old_records + records)
    emit(format_comparison(old_rep, new_rep))

    emit(_banner(f"Random audit ({args.sample_n}/{args.sample_n}, seed {args.seed})"))
    audit_text, audit_ok = audit(records, args.sample_n, args.seed, cfg)
    emit(audit_text)

    verdict_ready = (new_rep["accepted"] > 0 and audit_ok
                     and merged_rep["readiness"] >= old_rep["readiness"])

    emit(_banner("The 14 questions"))
    qa = answer_questions(old_rep, new_rep, merged_rep, cov_min, verdict_ready, ccfg)
    for q, a in qa:
        emit(f"  {q}")
        emit(f"     {a}")

    emit(_banner("FINAL VERDICT"))
    if verdict_ready:
        emit("  READY TO MERGE")
        emit(f"  - {new_rep['accepted']} new accepted clips "
             f"(+{new_rep['usable_hours'] * 60:.1f} min) pass the unmodified A0 gates")
        emit(f"  - audit clean; merged readiness {merged_rep['readiness']}/100 "
             f">= current {old_rep['readiness']}/100")
        emit("  (merge itself is deliberately NOT performed in this phase)")
    else:
        emit("  NEEDS MORE RECORDING")
        if new_rep["accepted"] == 0:
            emit("  - no new clip passed the A0 acceptance gates")
        if not audit_ok:
            emit("  - random audit found inconsistent records")
        if merged_rep["readiness"] < old_rep["readiness"]:
            emit(f"  - merging would LOWER readiness "
                 f"({old_rep['readiness']} -> {merged_rep['readiness']})")

    report_text = "\n".join(out) + "\n"
    (paths.reports / "a1_evaluation.txt").write_text(report_text, encoding="utf-8")
    (paths.reports / "a1_evaluation.json").write_text(json.dumps({
        "new": new_rep, "old": old_rep, "merged": merged_rep,
        "coverage_minutes": cov_min, "questions": qa,
        "verdict": "READY TO MERGE" if verdict_ready else "NEEDS MORE RECORDING",
    }, indent=2, default=str), encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
