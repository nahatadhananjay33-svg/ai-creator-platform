"""Validate the production voice dataset, checksum it, and build/verify a manifest.

Strictly read-only over the dataset directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

EXPECTED_DIRS = ["accepted_segments", "rejected_segments", "metadata", "reports"]
EXPECTED_METADATA = ["dataset.sqlite", "dataset.csv", "dataset.xlsx"]
MANIFEST_VERSION = 1


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _iter_files(root: Path) -> List[Path]:
    return sorted((p for p in Path(root).rglob("*") if p.is_file()),
                  key=lambda p: p.relative_to(root).as_posix())


def validate_structure(root: Path) -> dict:
    root = Path(root)
    missing_dirs = [d for d in EXPECTED_DIRS if not (root / d).is_dir()]
    missing_meta = [m for m in EXPECTED_METADATA if not (root / "metadata" / m).exists()]
    accepted = len(list((root / "accepted_segments").glob("*.wav"))) if (root / "accepted_segments").is_dir() else 0
    rejected = len(list((root / "rejected_segments").glob("*.wav"))) if (root / "rejected_segments").is_dir() else 0
    return {
        "root_exists": root.is_dir(),
        "missing_dirs": missing_dirs,
        "missing_metadata": missing_meta,
        "accepted_wavs": accepted,
        "rejected_wavs": rejected,
        "ok": root.is_dir() and not missing_dirs and not missing_meta and accepted > 0,
    }


def validate_metadata(root: Path) -> dict:
    """Cross-check the sqlite metadata against the wavs actually on disk."""
    root = Path(root)
    db = root / "metadata" / "dataset.sqlite"
    if not db.exists():
        return {"ok": False, "error": "dataset.sqlite missing"}
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM dataset")]
    finally:
        conn.close()

    acc = [r for r in rows if r.get("accepted")]
    disk_acc = {p.name for p in (root / "accepted_segments").glob("*.wav")}
    meta_acc = {Path(str(r.get("segment_file", ""))).name for r in acc}
    missing = sorted(meta_acc - disk_acc)
    orphans = sorted(disk_acc - meta_acc)
    hours = sum((r.get("duration") or 0) for r in acc) / 3600.0
    speech = sum((r.get("speech_duration") or 0) for r in acc) / 3600.0
    return {
        "ok": not missing and not orphans and len(acc) == len(disk_acc),
        "rows": len(rows), "accepted_rows": len(acc), "accepted_on_disk": len(disk_acc),
        "rejected_on_disk": len(list((root / "rejected_segments").glob("*.wav"))),
        "missing_on_disk": missing[:20], "missing_count": len(missing),
        "orphan_files": orphans[:20], "orphan_count": len(orphans),
        "accepted_hours": round(hours, 3), "accepted_speech_hours": round(speech, 3),
    }


def build_manifest(root: Path, progress: bool = True) -> dict:
    """sha256 + size for every file, relative to ``root`` (POSIX paths)."""
    root = Path(root)
    files = _iter_files(root)
    it = files
    if progress:
        try:
            from tqdm.auto import tqdm
            it = tqdm(files, desc="checksum", unit="file")
        except Exception:
            pass
    entries, total = [], 0
    for p in it:
        size = p.stat().st_size
        total += size
        entries.append({"path": p.relative_to(root).as_posix(), "bytes": size,
                        "sha256": sha256(p)})
    return {
        "manifest_version": MANIFEST_VERSION,
        "dataset_name": root.name,
        "source_root": str(root),
        "file_count": len(entries),
        "total_bytes": total,
        "total_mb": round(total / 1e6, 2),
        "structure": validate_structure(root),
        "metadata": validate_metadata(root),
        "files": entries,
    }


def write_manifest(manifest: dict, out_json: Path, out_csv: Optional[Path] = None) -> Path:
    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["path", "bytes", "sha256"])
            for e in manifest["files"]:
                w.writerow([e["path"], e["bytes"], e["sha256"]])
    return out_json


def load_manifest(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_against(manifest: dict, target_root: Path, quick: bool = False,
                   progress: bool = True) -> dict:
    """Verify an uploaded copy. quick=True checks presence+size only (fast over Drive)."""
    target_root = Path(target_root)
    entries = manifest["files"]
    it = entries
    if progress:
        try:
            from tqdm.auto import tqdm
            it = tqdm(entries, desc="verify", unit="file")
        except Exception:
            pass
    missing, size_mismatch, hash_mismatch, ok = [], [], [], 0
    for e in it:
        p = target_root / e["path"]
        if not p.exists():
            missing.append(e["path"])
            continue
        if p.stat().st_size != e["bytes"]:
            size_mismatch.append(e["path"])
            continue
        if not quick and sha256(p) != e["sha256"]:
            hash_mismatch.append(e["path"])
            continue
        ok += 1
    return {
        "target_root": str(target_root), "quick": quick,
        "expected_files": len(entries), "verified": ok,
        "missing": missing[:50], "missing_count": len(missing),
        "size_mismatch": size_mismatch[:50], "size_mismatch_count": len(size_mismatch),
        "hash_mismatch": hash_mismatch[:50], "hash_mismatch_count": len(hash_mismatch),
        "ok": not missing and not size_mismatch and not hash_mismatch,
    }
