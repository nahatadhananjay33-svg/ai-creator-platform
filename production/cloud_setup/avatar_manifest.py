"""Phase B0 — validate + checksum the PRODUCTION AVATAR dataset for upload.

Avatar counterpart of ``manifest.py`` (which handles the voice dataset).
Strictly read-only. The default upload scope is what training consumes:
``accepted/`` + ``thumbnails/`` + ``reports/`` + the metadata files at the
dataset root. Evaluation byproducts (``rejected/``, ``cropped_src/``,
``_recovery/`` — ~9.4 GB) are excluded unless ``include_all=True``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from .manifest import MANIFEST_VERSION, sha256

EXPECTED_DIRS = ["accepted", "rejected", "reports", "thumbnails"]
EXPECTED_METADATA = ["dataset.sqlite", "dataset.csv", "dataset.xlsx"]
UPLOAD_DIRS = ["accepted", "thumbnails", "reports"]      # + root metadata files


def validate_structure(root: Path) -> dict:
    root = Path(root)
    missing_dirs = [d for d in EXPECTED_DIRS if not (root / d).is_dir()]
    missing_meta = [m for m in EXPECTED_METADATA if not (root / m).exists()]
    accepted = len([p for p in (root / "accepted").glob("*") if p.is_file()]) \
        if (root / "accepted").is_dir() else 0
    rejected = len([p for p in (root / "rejected").glob("*") if p.is_file()]) \
        if (root / "rejected").is_dir() else 0
    return {
        "root_exists": root.is_dir(),
        "missing_dirs": missing_dirs,
        "missing_metadata": missing_meta,
        "accepted_files": accepted,
        "rejected_files": rejected,
        "ok": root.is_dir() and not missing_dirs and not missing_meta and accepted > 0,
    }


def validate_metadata(root: Path) -> dict:
    """Cross-check dataset.sqlite against the clips actually in accepted/."""
    root = Path(root)
    db = root / "dataset.sqlite"
    if not db.exists():
        return {"ok": False, "error": "dataset.sqlite missing"}
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM dataset")]
    finally:
        conn.close()

    acc = [r for r in rows if r.get("accepted")]
    disk = {p.name for p in (root / "accepted").glob("*") if p.is_file()}
    meta = {str(r.get("filename", "")) for r in acc}
    missing = sorted(meta - disk)
    orphans = sorted(disk - meta)
    minutes = sum((r.get("duration") or 0) for r in acc) / 60.0
    provenance = {"original": sum(1 for r in acc
                                  if str(r.get("source", "")).startswith("original:")),
                  "incremental": sum(1 for r in acc
                                     if str(r.get("source", "")).startswith("incremental:"))}
    return {
        "ok": not missing and not orphans and len(acc) == len(disk),
        "rows": len(rows), "accepted_rows": len(acc), "accepted_on_disk": len(disk),
        "missing_on_disk": missing[:20], "missing_count": len(missing),
        "orphan_files": orphans[:20], "orphan_count": len(orphans),
        "accepted_minutes": round(minutes, 1),
        "provenance": provenance,
    }


def upload_files(root: Path, include_all: bool = False) -> List[Path]:
    """The files the upload manifest covers, sorted by relative path."""
    root = Path(root)
    if include_all:
        files = [p for p in root.rglob("*") if p.is_file()]
    else:
        files = [root / m for m in EXPECTED_METADATA if (root / m).exists()]
        for d in UPLOAD_DIRS:
            if (root / d).is_dir():
                files += [p for p in (root / d).rglob("*") if p.is_file()]
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def build_avatar_manifest(root: Path, include_all: bool = False,
                          progress: bool = True) -> dict:
    root = Path(root)
    files = upload_files(root, include_all=include_all)
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
        "dataset_kind": "avatar",
        "source_root": str(root),
        "upload_scope": "all" if include_all else "training (accepted+thumbnails+reports+metadata)",
        "file_count": len(entries),
        "total_bytes": total,
        "total_gb": round(total / 1e9, 2),
        "structure": validate_structure(root),
        "metadata": validate_metadata(root),
        "files": entries,
    }
