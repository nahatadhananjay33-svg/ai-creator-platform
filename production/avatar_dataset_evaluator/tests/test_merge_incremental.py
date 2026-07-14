"""A2 merge: verdict gate, sha256 dedup, provenance, integrity — hermetic."""
from __future__ import annotations

import json

from production.avatar_dataset_evaluator import merge_incremental as mi
from production.avatar_dataset_evaluator.storage import load_records, write_csv, \
    write_sqlite, write_xlsx


def _dataset(root, records, verdict=None):
    """Materialize a dataset tree with real accepted files + thumbnails."""
    for d in ("accepted", "rejected", "reports", "thumbnails"):
        (root / d).mkdir(parents=True, exist_ok=True)
    for r in records:
        if r.accepted:
            (root / "accepted" / r.filename).write_bytes(
                f"video-bytes-{root.name}-{r.filename}".encode() * 50)
            thumb = root / "thumbnails" / (r.filename.rsplit(".", 1)[0] + ".jpg")
            thumb.write_bytes(b"jpg")
            r.thumbnail_path = str(thumb)
    write_sqlite(records, root / "dataset.sqlite")
    write_csv(records, root / "dataset.csv")
    write_xlsx(records, root / "dataset.xlsx")
    if verdict is not None:
        (root / "reports" / "a1_evaluation.json").write_text(
            json.dumps({"verdict": verdict}))
    return root


def _old(tmp_path, rec, n=5):
    records = [rec(filename=f"old{i}.mp4", duration=30.0) for i in range(n)]
    records += [rec(filename="oldrej.mp4", accepted=False, quality="reject",
                    accept_reason="", reject_reason="no visible face")]
    for i, r in enumerate(records, 1):
        r.id = i
    return _dataset(tmp_path / "avatar_dataset", records)


def _new(tmp_path, rec, dup_of=None):
    records = [rec(filename="new1.mp4", duration=20.0, expression="smiling"),
               rec(filename="new2.mp4", duration=25.0),
               rec(filename="newrej.mp4", accepted=False, quality="reject",
                   accept_reason="", reject_reason="heavy blur")]
    for i, r in enumerate(records, 1):
        r.id = i
    root = _dataset(tmp_path / "avatar_dataset_new", records, verdict="READY TO MERGE")
    if dup_of:                     # make new2 a byte-copy of an old accepted file
        (root / "accepted" / "new2.mp4").write_bytes(dup_of.read_bytes())
    return root


def test_structure_and_verdict_gates(tmp_path, rec):
    old = _old(tmp_path, rec)
    assert mi.validate_structure(old) == []
    assert mi.validate_structure(tmp_path / "nothing") == mi.REQUIRED

    new = _new(tmp_path, rec)
    assert mi.read_verdict(new) == "READY TO MERGE"
    (new / "reports" / "a1_evaluation.json").write_text(
        json.dumps({"verdict": "NEEDS MORE RECORDING"}))
    rc = mi.run(["--old", str(old), "--new", str(new)])
    assert rc == 1                                     # aborts on wrong verdict


def test_merge_dedups_marks_provenance_and_validates(tmp_path, rec):
    old = _old(tmp_path, rec)
    new = _new(tmp_path, rec, dup_of=old / "accepted" / "old1.mp4")

    stats = mi.merge(old, new)
    assert stats["added"] == 1                          # new1 only
    assert stats["duplicates_skipped"] == 1             # new2 == old1 bytes
    assert (old / "accepted" / "new1.mp4").exists()
    assert not (old / "accepted" / "new2.mp4").exists()
    assert not (old / "accepted" / "newrej.mp4").exists()   # rejected never copied
    assert (old / "reports" / "premerge_a2" / "dataset.sqlite").exists()
    assert (old / "thumbnails" / "new1.jpg").exists()

    rows = load_records(old / "dataset.sqlite")
    assert len(rows) == 7                               # 6 old + 1 added
    assert [r.id for r in rows] == list(range(1, 8))
    assert all(r.source.startswith(("original:", "incremental:")) for r in rows)
    incr = [r for r in rows if r.source.startswith("incremental:")]
    assert [r.filename for r in incr] == ["new1.mp4"]

    checks, notes = mi.integrity(old, stats["old_accepted"], stats["added"])
    assert all(checks.values()), checks

    stats2 = mi.merge(old, new)                         # idempotent re-run
    assert stats2["added"] == 0 and stats2["duplicates_skipped"] == 2


def test_name_collision_gets_suffixed(tmp_path, rec):
    old = _old(tmp_path, rec)
    new = _new(tmp_path, rec)
    # same NAME as an old file but different content
    (new / "accepted" / "old1.mp4").write_bytes(b"different content" * 40)
    recs = load_records(new / "dataset.sqlite")
    extra = rec(filename="old1.mp4", duration=15.0)
    extra.id = len(recs) + 1
    write_sqlite(recs + [extra], new / "dataset.sqlite")

    stats = mi.merge(old, new)
    assert (old / "accepted" / "old1__a1.mp4").exists()
    names = {r.filename for r in stats["merged_records"] if r.accepted}
    assert "old1__a1.mp4" in names


def test_full_run_prints_final_summary(tmp_path, rec, capsys):
    old = _old(tmp_path, rec)
    new = _new(tmp_path, rec)
    rc = mi.run(["--old", str(old), "--new", str(new),
                 "--report-copy", str(tmp_path / "MERGE_REPORT.md")])
    assert rc == 0
    text = capsys.readouterr().out
    for marker in ("STEP 1", "STEP 2", "STEPS 3+4", "STEP 5", "STEP 7",
                   "PRODUCTION AVATAR DATASET UPDATED",
                   "Rejected clips merged   : 0",
                   "Avatar Readiness Score", "[OK]"):
        assert marker in text, marker
    assert "[FAIL]" not in text
    assert (old / "reports" / "MERGE_REPORT.md").exists()
    assert (tmp_path / "MERGE_REPORT.md").exists()
