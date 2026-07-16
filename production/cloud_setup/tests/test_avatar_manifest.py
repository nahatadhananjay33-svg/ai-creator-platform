"""Avatar dataset validation, upload scope, and manifest/verify round-trip."""
from __future__ import annotations

import sqlite3

from production.cloud_setup.avatar_manifest import (build_avatar_manifest,
                                                    upload_files,
                                                    validate_metadata,
                                                    validate_structure)
from production.cloud_setup.manifest import verify_against


def _avatar_dataset(root, accepted=("a.mp4", "b.mov"), orphan=False, missing=False):
    for d in ("accepted", "rejected", "reports", "thumbnails",
              "cropped_src", "_recovery"):
        (root / d).mkdir(parents=True, exist_ok=True)
    rows = []
    for i, name in enumerate(accepted, 1):
        if not (missing and i == 1):
            (root / "accepted" / name).write_bytes(f"clip-{name}".encode() * 100)
        (root / "thumbnails" / (name.rsplit(".", 1)[0] + ".jpg")).write_bytes(b"jpg")
        rows.append((i, name, f"original:{name}", 1, 10.0))
    rows.append((len(rows) + 1, "rej.mp4", "original:rej.mp4", 0, 5.0))
    (root / "rejected" / "rej.mp4").write_bytes(b"rejected" * 50)
    (root / "cropped_src" / "crop.mp4").write_bytes(b"crop" * 50)
    if orphan:
        (root / "accepted" / "orphan.mp4").write_bytes(b"orphan" * 50)
    (root / "reports" / "report.txt").write_text("report")

    conn = sqlite3.connect(str(root / "dataset.sqlite"))
    conn.execute("CREATE TABLE dataset (id INTEGER, filename TEXT, source TEXT, "
                 "accepted INTEGER, duration REAL)")
    conn.executemany("INSERT INTO dataset VALUES (?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    (root / "dataset.csv").write_text("stub")
    (root / "dataset.xlsx").write_bytes(b"stub")
    return root


def test_validate_structure_and_metadata_clean(tmp_path):
    root = _avatar_dataset(tmp_path / "avatar_dataset")
    st = validate_structure(root)
    assert st["ok"] and st["accepted_files"] == 2 and st["rejected_files"] == 1
    md = validate_metadata(root)
    assert md["ok"] and md["accepted_rows"] == 2 == md["accepted_on_disk"]
    assert md["provenance"] == {"original": 2, "incremental": 0}


def test_validate_metadata_catches_missing_and_orphans(tmp_path):
    md = validate_metadata(_avatar_dataset(tmp_path / "m", missing=True))
    assert not md["ok"] and md["missing_count"] == 1
    md2 = validate_metadata(_avatar_dataset(tmp_path / "o", orphan=True))
    assert not md2["ok"] and md2["orphan_count"] == 1
    assert validate_structure(tmp_path / "nowhere")["ok"] is False


def test_upload_scope_excludes_byproducts_by_default(tmp_path):
    root = _avatar_dataset(tmp_path / "avatar_dataset")
    rel = {p.relative_to(root).as_posix() for p in upload_files(root)}
    assert "accepted/a.mp4" in rel and "dataset.sqlite" in rel
    assert "thumbnails/a.jpg" in rel and "reports/report.txt" in rel
    assert not any(p.startswith(("rejected/", "cropped_src/", "_recovery/"))
                   for p in rel)
    rel_all = {p.relative_to(root).as_posix()
               for p in upload_files(root, include_all=True)}
    assert "rejected/rej.mp4" in rel_all and "cropped_src/crop.mp4" in rel_all


def test_manifest_verify_roundtrip_detects_corruption(tmp_path):
    root = _avatar_dataset(tmp_path / "avatar_dataset")
    man = build_avatar_manifest(root, progress=False)
    assert man["dataset_kind"] == "avatar" and man["file_count"] == len(man["files"])

    upload = tmp_path / "drive_copy"
    for e in man["files"]:
        dst = upload / e["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes((root / e["path"]).read_bytes())
    assert verify_against(man, upload, progress=False)["ok"]

    (upload / "accepted" / "a.mp4").write_bytes(b"corrupted" * 100)
    res = verify_against(man, upload, progress=False)
    assert not res["ok"]
    assert res["size_mismatch_count"] + res["hash_mismatch_count"] >= 1
