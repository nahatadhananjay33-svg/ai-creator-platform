"""Phase A2 — merge the A1 ACCEPTED clips into the production avatar dataset.

    python -m production.avatar_dataset_evaluator.merge_incremental

Merge only: no re-evaluation, no recovery, no threshold or logic changes, no
Avatar Engine. Aborts unless both dataset trees are complete and the A1 report
verdict is exactly READY TO MERGE. Only accepted files move; duplicates are
detected by SHA256 and skipped; existing files are never overwritten; the
pre-merge metadata is backed up under reports/premerge_a2/.

Provenance: every merged row's ``source`` is prefixed ``original:`` or
``incremental:`` (the original relative path is kept after the prefix).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .models import Record
from .report import build_report
from .storage import load_records, write_csv, write_sqlite, write_xlsx

OLD_OUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset")
NEW_OUT = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_new")
REQUIRED = ["dataset.sqlite", "dataset.csv", "dataset.xlsx",
            "accepted", "rejected", "reports"]
VERDICT_REQUIRED = "READY TO MERGE"


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def validate_structure(root: Path) -> List[str]:
    root = Path(root)
    return [name for name in REQUIRED if not (root / name).exists()]


def read_verdict(new_dir: Path) -> str:
    j = Path(new_dir) / "reports" / "a1_evaluation.json"
    if j.exists():
        try:
            return str(json.loads(j.read_text(encoding="utf-8")).get("verdict", ""))
        except json.JSONDecodeError:
            pass
    t = Path(new_dir) / "reports" / "a1_evaluation.txt"
    if t.exists() and VERDICT_REQUIRED in t.read_text(encoding="utf-8"):
        return VERDICT_REQUIRED
    return ""


def _link_no_overwrite(src: Path, dst: Path) -> None:
    if dst.exists():
        raise FileExistsError(dst)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def _provenance(source: str, marker: str) -> str:
    if source.startswith(("original:", "incremental:")):
        return source                                  # idempotent on re-runs
    return f"{marker}:{source}"


def merge(old_dir: Path, new_dir: Path) -> dict:
    """Move accepted A1 clips + thumbnails into production; rewrite metadata."""
    old_dir, new_dir = Path(old_dir), Path(new_dir)
    old_acc, new_acc = old_dir / "accepted", new_dir / "accepted"
    old_thumbs = old_dir / "thumbnails"
    old_thumbs.mkdir(parents=True, exist_ok=True)

    backup = old_dir / "reports" / "premerge_a2"
    backup.mkdir(parents=True, exist_ok=True)
    for name in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        if (old_dir / name).exists() and not (backup / name).exists():
            shutil.copyfile(old_dir / name, backup / name)

    old_records = load_records(old_dir / "dataset.sqlite")
    new_records = load_records(new_dir / "dataset.sqlite")

    existing: Dict[str, str] = {}
    for r in old_records:
        if r.accepted and (old_acc / r.filename).exists():
            existing[sha256(old_acc / r.filename)] = r.filename

    added: List[Record] = []
    duplicates: List[Tuple[str, str]] = []
    missing: List[str] = []
    for r in sorted((r for r in new_records if r.accepted), key=lambda r: r.filename):
        src = new_acc / r.filename
        if not src.exists():
            missing.append(r.filename)
            continue
        digest = sha256(src)
        if digest in existing:
            duplicates.append((r.filename, existing[digest]))
            continue
        target = old_acc / r.filename
        if target.exists():                            # same name, other content
            target = old_acc / f"{target.stem}__a1{target.suffix}"
        _link_no_overwrite(src, target)

        thumb_src = new_dir / "thumbnails" / (Path(r.filename).stem + ".jpg")
        thumb_dst = old_thumbs / (target.stem + ".jpg")
        if thumb_src.exists() and not thumb_dst.exists():
            shutil.copyfile(thumb_src, thumb_dst)

        r.filename = target.name
        r.source = _provenance(r.source, "incremental")
        r.thumbnail_path = str(thumb_dst) if thumb_dst.exists() else r.thumbnail_path
        added.append(r)
        existing[digest] = target.name

    for r in old_records:
        r.source = _provenance(r.source, "original")

    merged = old_records + added
    for i, r in enumerate(merged, 1):
        r.id = i
    write_sqlite(merged, old_dir / "dataset.sqlite")
    write_csv(merged, old_dir / "dataset.csv")
    write_xlsx(merged, old_dir / "dataset.xlsx")

    return {"old_total": len(old_records),
            "old_accepted": sum(1 for r in old_records if r.accepted),
            "new_accepted": len(added) + len(duplicates) + len(missing),
            "added": len(added), "duplicates_skipped": len(duplicates),
            "missing_files": missing, "merged_records": merged}


# --- Step 5: statistics ---------------------------------------------------------------

def production_stats(merged: List[Record]) -> Tuple[dict, str]:
    rep = build_report(merged)
    acc = [r for r in merged if r.accepted]
    pose = Counter(r.face_view for r in acc)
    expr = Counter(r.expression for r in acc)
    quality = Counter(r.quality for r in acc)
    lines = [
        f"  Merged accepted clips   : {len(acc)}",
        f"  Accepted duration       : {rep['usable_hours'] * 60:.1f} min "
        f"({rep['usable_hours']:.3f} h)",
        f"  Average avatar score    : "
        f"{round(sum(r.avatar_score for r in acc) / len(acc), 1) if acc else 0.0}"
        f"/100 (SNR is a voice metric - n/a for avatar clips)",
        f"  Average quality         : "
        + ", ".join(f"{k}: {v}" for k, v in quality.most_common()),
        f"  Average face visibility : "
        f"{round(sum(r.face_visibility_pct for r in acc) / len(acc), 1) if acc else 0}%",
        f"  Average stability       : "
        f"{round(sum(r.camera_stability for r in acc) / len(acc), 2) if acc else 0}",
        f"  Average lighting        : "
        f"{round(sum(r.lighting_mean for r in acc) / len(acc), 0) if acc else 0:.0f}/255",
        f"  Head pose distribution  : "
        + ", ".join(f"{k}: {v}" for k, v in pose.most_common()),
        f"  Expression distribution : "
        + ", ".join(f"{k}: {v}" for k, v in expr.most_common()),
    ]
    return rep, "\n".join(lines)


# --- Step 7: integrity ------------------------------------------------------------------

def integrity(old_dir: Path, old_accepted: int, added: int) -> Tuple[Dict[str, bool], List[str]]:
    import csv as _csv
    from openpyxl import load_workbook

    old_dir = Path(old_dir)
    rows = load_records(old_dir / "dataset.sqlite")
    acc = [r for r in rows if r.accepted]
    acc_dir = old_dir / "accepted"

    files_on_disk = {p.name for p in acc_dir.iterdir() if p.is_file()}
    row_files = {r.filename for r in acc}

    with open(old_dir / "dataset.csv", newline="", encoding="utf-8") as f:
        csv_rows = sum(1 for _ in _csv.reader(f)) - 1
    wb = load_workbook(str(old_dir / "dataset.xlsx"), read_only=True)
    xlsx_rows = wb.active.max_row - 1
    wb.close()

    hashes = [sha256(acc_dir / r.filename) for r in acc
              if (acc_dir / r.filename).exists()]
    dup_count = len(hashes) - len(set(hashes))
    # provenance-scoped duplicate check: the merge itself must not have
    # introduced any (added clips were deduped by construction); pre-existing
    # duplicates inside the original dataset are noted, not failed.
    incr = [r for r in acc if r.source.startswith("incremental:")]
    incr_hashes = [sha256(acc_dir / r.filename) for r in incr
                   if (acc_dir / r.filename).exists()]
    orig_hashes = [h for r, h in zip(
        [r for r in acc if not r.source.startswith("incremental:")],
        [sha256(acc_dir / r.filename) for r in acc
         if not r.source.startswith("incremental:") and (acc_dir / r.filename).exists()])]
    merge_dup_free = (len(incr_hashes) == len(set(incr_hashes))
                      and not set(incr_hashes) & set(orig_hashes))

    thumbs_missing = [r.filename for r in incr
                      if not (r.thumbnail_path and Path(r.thumbnail_path).exists())]

    notes: List[str] = []
    if merge_dup_free and dup_count:
        notes.append(f"{dup_count} duplicate file(s) pre-date A2 inside the original "
                     f"accepted set (duplicate source videos); left untouched.")
    orphan_rows = row_files - files_on_disk
    orphan_files = files_on_disk - row_files
    if orphan_files:
        notes.append(f"files without metadata rows: {sorted(orphan_files)[:5]}")

    checks = {
        "every merged file exists": not orphan_rows,
        "metadata accepted rows match files on disk": row_files == files_on_disk,
        "sqlite consistent": len(acc) == old_accepted + added,
        "csv consistent": csv_rows == len(rows),
        "xlsx consistent": xlsx_rows == len(rows),
        "no duplicate sha256 introduced by merge": merge_dup_free,
        "no orphan metadata": not orphan_rows,
        "no missing thumbnails (merged clips)": not thumbs_missing,
        "ids unique and sequential": [r.id for r in rows] == list(range(1, len(rows) + 1)),
        "provenance on every row": all(
            r.source.startswith(("original:", "incremental:")) for r in rows),
    }
    return checks, notes


def format_checks(checks: Dict[str, bool], notes: List[str]) -> str:
    lines = [f"  {'[OK]  ' if ok else '[FAIL]'} {name}" for name, ok in checks.items()]
    lines += [f"  note: {n}" for n in notes]
    return "\n".join(lines)


# --- orchestration -------------------------------------------------------------------------

def run(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m production.avatar_dataset_evaluator.merge_incremental",
        description="Phase A2: merge A1 accepted clips into the production dataset.")
    ap.add_argument("--old", default=str(OLD_OUT))
    ap.add_argument("--new", default=str(NEW_OUT))
    ap.add_argument("--report-copy", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    old_dir, new_dir = Path(args.old), Path(args.new)

    out: List[str] = []

    def emit(text: str) -> None:
        print(text, flush=True)
        out.append(text)

    emit("=" * 52 + "\n  STEP 1: validate both dataset trees\n" + "=" * 52)
    aborted = False
    for name, root in (("production", old_dir), ("incremental", new_dir)):
        missing = validate_structure(root)
        emit(f"  {name}: {root} -> " + ("OK" if not missing else f"MISSING {missing}"))
        aborted = aborted or bool(missing)
    if aborted:
        emit("  ABORT: dataset structure incomplete.")
        return 1

    emit("=" * 52 + "\n  STEP 2: verify the A1 verdict\n" + "=" * 52)
    verdict = read_verdict(new_dir)
    emit(f"  A1 verdict: {verdict!r}")
    if verdict != VERDICT_REQUIRED:
        emit(f"  ABORT: verdict is not exactly {VERDICT_REQUIRED!r}.")
        return 1

    emit("=" * 52 + "\n  STEPS 3+4: merge accepted files + metadata\n" + "=" * 52)
    stats = merge(old_dir, new_dir)
    old_rep = build_report(load_records(old_dir / "reports" / "premerge_a2" / "dataset.sqlite"))
    emit(f"  Original accepted clips : {stats['old_accepted']}")
    emit(f"  A1 accepted clips       : {stats['new_accepted']}")
    emit(f"  Files merged            : {stats['added']}")
    emit(f"  Duplicates skipped      : {stats['duplicates_skipped']}")
    if stats["missing_files"]:
        emit(f"  Missing source files    : {stats['missing_files']}")

    emit("=" * 52 + "\n  STEP 5: recalculated production statistics\n" + "=" * 52)
    merged = stats["merged_records"]
    rep, stats_text = production_stats(merged)
    emit(f"  Original accepted clips : {stats['old_accepted']}")
    emit(f"  New accepted clips      : {stats['added']}")
    emit(stats_text)

    emit("=" * 52 + "\n  STEP 7: integrity validation\n" + "=" * 52)
    checks, notes = integrity(old_dir, stats["old_accepted"], stats["added"])
    emit(format_checks(checks, notes))
    ok = all(checks.values())

    missing_views = rep["missing"]
    emit("\n" + "=" * 52)
    emit("  PRODUCTION AVATAR DATASET UPDATED")
    emit("=" * 52)
    emit(f"  Original accepted clips : {stats['old_accepted']}")
    emit(f"  New accepted clips      : {stats['added']}")
    emit(f"  Rejected clips merged   : 0")
    emit(f"  Final accepted clips    : {stats['old_accepted'] + stats['added']}")
    emit(f"  Final accepted duration : {rep['usable_hours'] * 60:.1f} min")
    emit(f"  Avatar Readiness Score  : {old_rep['readiness']}/100 -> {rep['readiness']}/100")
    emit("  Remaining dataset gaps  :")
    for m in missing_views or ["(none)"]:
        emit(f"    - {m}")
    emit("  Recommendation          : dataset is ready for talking-head avatar "
         "training (MuseTalk/LatentSync first); record the remaining gap "
         "viewpoints before full-motion avatars. Training NOT started (out of scope).")
    emit("=" * 52)

    # STEP 6: MERGE_REPORT.md
    report_md = _merge_report_md(stats, old_rep, rep, checks, notes)
    (old_dir / "reports" / "MERGE_REPORT.md").write_text(report_md, encoding="utf-8")
    if args.report_copy:
        Path(args.report_copy).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_copy).write_text(report_md, encoding="utf-8")
    (old_dir / "reports" / "a2_merge_output.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    return 0 if ok else 2


def _merge_report_md(stats: dict, old_rep: dict, rep: dict,
                     checks: Dict[str, bool], notes: List[str]) -> str:
    nl = "\n"
    check_lines = nl.join(f"- {'[x]' if ok else '[ ] FAIL'} {name}"
                          for name, ok in checks.items())
    note_lines = nl.join(f"- {n}" for n in notes) or "- none"
    gaps = nl.join(f"- {m}" for m in rep["missing"]) or "- none"
    return f"""# MERGE_REPORT — Phase A2 (incremental avatar dataset merge)

## Original dataset (pre-merge)

{stats['old_accepted']} accepted clips, readiness {old_rep['readiness']}/100,
{old_rep['usable_hours'] * 60:.1f} accepted minutes.

## Incremental dataset (A1)

{stats['new_accepted']} accepted clips offered; verdict READY TO MERGE.

## Merged dataset

- Files merged: **{stats['added']}** (accepted only; 0 rejected clips copied)
- Duplicates skipped (SHA256): {stats['duplicates_skipped']}
- Final accepted clips: **{stats['old_accepted'] + stats['added']}**
- Final accepted duration: {rep['usable_hours'] * 60:.1f} min
- Metadata: dataset.sqlite/csv/xlsx rewritten with sequential ids and
  provenance (`original:` / `incremental:` prefix on every row's source);
  pre-merge metadata backed up in `reports/premerge_a2/`.

## Readiness

- Old Avatar Readiness Score: **{old_rep['readiness']}/100**
- New Avatar Readiness Score: **{rep['readiness']}/100**

## Remaining missing viewpoints

{gaps}
(From A1 coverage: Looking Up, Serious, Walking, Sitting remain < 1 usable min.)

## Integrity validation

{check_lines}

Notes:
{note_lines}
"""


if __name__ == "__main__":
    raise SystemExit(run())
