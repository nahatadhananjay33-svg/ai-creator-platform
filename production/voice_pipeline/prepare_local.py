"""Local dataset preparation CLI (Windows/local).

Automates: create folder structure -> move Tanshi ZIPs out of Downloads ->
extract each into its own folder -> print stats -> run the EXISTING Voice
Dataset Builder (via the glue's run_pipeline) -> validation, audit, final report.

Reuses production.voice_dataset unchanged. Nothing here modifies any engine.

    python -m production.voice_pipeline.prepare_local

Large media lives under the data base (default D:\\AI_CREATOR_DATA\\Tanshi),
never inside the git repo.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sqlite3
import subprocess
import time
import zipfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from production.voice_dataset.config import MEDIA_EXTS

from .glue import _list_media, format_report, run_pipeline

DEFAULT_BASE = r"D:\AI_CREATOR_DATA\Tanshi"
DEFAULT_DOWNLOADS = str(Path.home() / "Downloads")
ZIP_PATTERN = "Tanshi_raw_videos*.zip"

STRUCTURE = ["raw_videos", "voice_dataset/accepted", "voice_dataset/rejected",
             "voice_dataset/metadata", "voice_models", "avatar_dataset", "exports"]


# --- steps -------------------------------------------------------------------
def ensure_structure(base: Path) -> None:
    for sub in STRUCTURE:
        (base / sub).mkdir(parents=True, exist_ok=True)


def move_zips(downloads: Path, dest: Path, pattern: str = ZIP_PATTERN) -> Tuple[List[str], int]:
    dest.mkdir(parents=True, exist_ok=True)
    moved, total = [], 0
    for z in sorted(Path(downloads).glob(pattern)):
        target = dest / z.name
        if target.exists():                       # already moved (resume)
            continue
        total += z.stat().st_size
        shutil.move(str(z), str(target))          # MOVE, not copy
        moved.append(target.name)
    return moved, total


def extract_zips(raw_dir: Path) -> Tuple[List[str], List[str]]:
    extracted, skipped = [], []
    for z in sorted(Path(raw_dir).glob("*.zip")):
        out = raw_dir / z.stem                    # each ZIP -> its own folder
        if out.exists() and any(out.iterdir()):
            skipped.append(z.name)                # already extracted (resume)
            continue
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(out)
        extracted.append(z.name)
    return extracted, skipped


def _probe_seconds(p: Path) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", str(p)], capture_output=True, text=True, timeout=30)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def stats(raw_dir: Path) -> dict:
    raw_dir = Path(raw_dir)
    folders = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    vids = _list_media(raw_dir)
    total = sum(p.stat().st_size for p in vids)
    sample = vids[:15]
    ssec = sum(_probe_seconds(p) for p in sample)
    smb = (sum(p.stat().st_size for p in sample) / 1e6) or 1.0
    est_h = (ssec / smb) * (total / 1e6) / 3600.0
    exts = sorted({p.suffix.lower() for p in vids})
    return {"folders": len(folders), "videos": len(vids),
            "storage_gb": round(total / 1e9, 2), "est_hours": round(est_h, 1),
            "formats": exts}


def audit(dataset_sqlite: Path, n: int = 20, seed: int = 0):
    conn = sqlite3.connect(str(dataset_sqlite))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT filename, duration, quality, accepted, reason FROM dataset")]
    finally:
        conn.close()
    acc = [r for r in rows if r["accepted"]]
    rej = [r for r in rows if not r["accepted"]]
    rng = random.Random(seed)
    return rng.sample(acc, min(n, len(acc))), rng.sample(rej, min(n, len(rej)))


def _dir_size_gb(path: Path) -> float:
    return round(sum(p.stat().st_size for p in Path(path).rglob("*") if p.is_file()) / 1e9, 2)


# --- orchestration -----------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m production.voice_pipeline.prepare_local",
                                 description="Prepare the local voice dataset from downloaded ZIPs.")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--downloads", default=DEFAULT_DOWNLOADS)
    ap.add_argument("--creator", default="tanshi")
    ap.add_argument("--no-move", action="store_true", help="skip moving ZIPs from Downloads")
    ap.add_argument("--skip-process", action="store_true", help="stop after extraction + stats")
    ap.add_argument("--audit-n", type=int, default=20)
    args = ap.parse_args(argv)

    base = Path(args.base)
    raw = base / "raw_videos"
    out = base / "voice_dataset"
    workspace = base / "_workspace"
    t0 = time.time()

    print("── STEP 1: folder structure")
    ensure_structure(base)
    print(f"  ✓ {base}")

    moved, moved_bytes = ([], 0)
    if not args.no_move:
        print("── STEP 2: move ZIPs from Downloads")
        moved, moved_bytes = move_zips(Path(args.downloads), raw)
        print(f"  ✓ moved {len(moved)} ZIP(s), {moved_bytes/1e9:.2f} GB")

    print("── STEP 3: extract ZIPs")
    extracted, skipped = extract_zips(raw)
    print(f"  ✓ extracted {len(extracted)}, skipped {len(skipped)} (already present)")

    print("── STEP 4: dataset statistics")
    st = stats(raw)
    print(f"  Folders discovered : {st['folders']}")
    print(f"  Videos discovered  : {st['videos']}")
    print(f"  Total storage      : {st['storage_gb']} GB")
    print(f"  Estimated duration : ~{st['est_hours']} hours")
    print(f"  Formats            : {', '.join(st['formats']) or '(none)'}")

    if args.skip_process or st["videos"] == 0:
        print("\n(stopping before processing)" if args.skip_process else "\nNo videos to process.")
        return 0

    print("── STEP 5-6: run Voice Dataset Builder (reused; resumable)")
    summary = run_pipeline(raw, workspace, out, creator=args.creator,
                           resume=True, progress=True)

    print("\n── STEP 7: validation")
    print(format_report(summary))

    print("\n── STEP 8: manual audit (random sample)")
    acc, rej = audit(out / "metadata" / "dataset.sqlite", n=args.audit_n)
    print(f"  ACCEPTED sample ({len(acc)}):")
    for r in acc:
        print(f"    {r['filename'][:45]:45} {r['duration']:7.1f}s  {r['quality']:9}  {r['reason'][:50]}")
    print(f"  REJECTED sample ({len(rej)}):")
    for r in rej:
        print(f"    {r['filename'][:45]:45} {r['duration']:7.1f}s  {r['reason'][:60]}")

    print("\n── STEP 9: final report")
    ds_gb = _dir_size_gb(out)
    acc_rate = summary["accepted_clips"] / max(1, summary["total_videos"])
    suitable = summary["accepted_speech_hours"] >= 1.0 and acc_rate >= 0.3
    print(f"  ZIP files moved      : {len(moved)}")
    print(f"  ZIP files extracted  : {len(extracted)} (+{len(skipped)} already)")
    print(f"  Folders              : {st['folders']}")
    print(f"  Videos processed     : {summary['videos_processed']} (skipped {summary['videos_skipped']})")
    print(f"  Accepted speech hours: {summary['accepted_speech_hours']:.3f}")
    print(f"  Rejected speech hours: {summary['rejected_speech_hours']:.3f}")
    print(f"  Dataset location     : {out}")
    print(f"  Voice dataset size   : {ds_gb} GB")
    print(f"  Total time           : {(time.time()-t0)/60:.1f} min")
    print(f"  Suitable for cloning : {'YES' if suitable else 'NOT YET'} "
          f"(acceptance {acc_rate*100:.0f}%, {summary['accepted_speech_hours']:.2f} h)")
    if not suitable:
        top = summary["top_rejection_reasons"][0][0] if summary["top_rejection_reasons"] else "n/a"
        print(f"  Recommended next     : acceptance is low; dominant reject reason is "
              f"'{top}'. Review/adjust that filter in a separate, approved change "
              f"(this phase must not modify the builder), then re-run (resumable).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
