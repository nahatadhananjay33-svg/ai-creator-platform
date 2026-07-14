"""Report aggregation + storage round-trip."""
from __future__ import annotations

import csv
import sqlite3

from production.avatar_dataset_evaluator.models import RECORD_COLUMNS
from production.avatar_dataset_evaluator.report import build_report, format_report
from production.avatar_dataset_evaluator.storage import (load_records, write_csv,
                                                         write_sqlite, write_xlsx)


def test_report(rec):
    recs = ([rec(id=i, filename=f"a{i}.mp4", accepted=True, face_view="frontal",
                 expression="talking", duration=60.0) for i in range(40)]
            + [rec(id=100 + i, filename=f"r{i}.mp4", accepted=False, quality="reject",
                   reject_reason="no visible face") for i in range(10)])
    rep = build_report(recs)
    assert rep["total"] == 50 and rep["accepted"] == 40 and rep["rejected"] == 10
    assert rep["diversity"]["front_facing"] == 40
    assert 0 <= rep["readiness"] <= 100
    assert set(rep["models"]) == {"MuseTalk", "LatentSync", "EchoMimic", "Hallo2"}
    assert any("side-profile" in m for m in rep["missing"])   # no profiles present
    assert "AVATAR READINESS SCORE" in format_report(rep)


def test_storage_roundtrip(tmp_path, rec):
    recs = [rec(id=1, filename="a.mp4", accepted=True),
            rec(id=2, filename="b.mp4", accepted=False, reject_reason="too short")]
    db = write_sqlite(recs, tmp_path / "dataset.sqlite")
    write_csv(recs, tmp_path / "dataset.csv")
    write_xlsx(recs, tmp_path / "dataset.xlsx")

    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(dataset)")]
    accepted = conn.execute("SELECT accepted FROM dataset ORDER BY id").fetchall()
    conn.close()
    assert cols == RECORD_COLUMNS
    assert accepted == [(1,), (0,)]

    with open(tmp_path / "dataset.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == RECORD_COLUMNS and len(rows) == 3

    loaded = load_records(db)          # reload for resume
    assert len(loaded) == 2 and loaded[0].accepted is True and loaded[1].accepted is False
