"""Persist per-video Records to SQLite / CSV / XLSX, and reload for resume."""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import List

from .models import RECORD_COLUMNS, Record

_SQL_TYPES = {
    "id": "INTEGER PRIMARY KEY", "duration": "REAL", "fps": "REAL",
    "aspect_ratio": "REAL", "file_size_mb": "REAL", "bitrate": "INTEGER",
    "frame_count": "INTEGER", "width": "INTEGER", "height": "INTEGER",
    "scene_changes": "INTEGER", "accepted": "INTEGER", "avatar_score": "REAL",
}
_FLOAT = {"face_visibility_pct", "avg_face_size_pct", "frontal_pct", "profile_pct",
          "lighting_mean", "lighting_consistency", "camera_stability", "motion_blur",
          "occlusion_pct", "eye_visibility_pct", "mouth_visibility_pct", "speaking_pct",
          "walking_pct", "stationary_pct", "camera_movement"}
for _c in _FLOAT:
    _SQL_TYPES[_c] = "REAL"
_BOOL_COLS = {"accepted"}


def _row(rec: Record) -> list:
    d = rec.as_dict()
    return [int(d[c]) if c in _BOOL_COLS else d[c] for c in RECORD_COLUMNS]


def write_sqlite(records: List[Record], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    cols = ", ".join(f"{c} {_SQL_TYPES.get(c, 'TEXT')}" for c in RECORD_COLUMNS)
    ph = ", ".join("?" for _ in RECORD_COLUMNS)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute(f"CREATE TABLE dataset ({cols})")
        conn.executemany(f"INSERT INTO dataset ({', '.join(RECORD_COLUMNS)}) VALUES ({ph})",
                         [_row(r) for r in records])
        conn.commit()
    finally:
        conn.close()
    return path


def write_csv(records: List[Record], path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(RECORD_COLUMNS)
        for r in records:
            w.writerow(_row(r))
    return path


def write_xlsx(records: List[Record], path: Path) -> Path:
    from openpyxl import Workbook
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "avatar_dataset"
    ws.append(RECORD_COLUMNS)
    for r in records:
        ws.append(_row(r))
    wb.save(str(path))
    return path


def load_records(path: Path) -> List[Record]:
    path = Path(path)
    if not path.exists():
        return []
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM dataset")]
    except Exception:
        return []
    finally:
        conn.close()
    out = []
    for row in rows:
        kw = {c: (bool(row[c]) if c in _BOOL_COLS else row[c]) for c in RECORD_COLUMNS}
        out.append(Record(**kw))
    return out
