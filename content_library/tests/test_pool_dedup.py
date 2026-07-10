"""Content-pool deduplication tests (Phase C17) — hermetic and deterministic.

Adding the same content twice must not duplicate bytes on disk; removal is
reference-counted so a shared file survives until its last referrer is gone.
"""
from __future__ import annotations


def _files(library) -> list[str]:
    files_dir = library.assets.dir / "files"
    return sorted(p.name for p in files_dir.iterdir()) if files_dir.exists() else []


def test_identical_content_stored_once(library, tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"                       # same bytes, different name
    a.write_bytes(b"PNGDATA" * 16)
    b.write_bytes(b"PNGDATA" * 16)
    first = library.assets.add("Logo A", source=a, kind="image")
    second = library.assets.add("Logo B", source=b, kind="image")

    assert len(_files(library)) == 1             # only one physical file on disk
    assert first.path == second.path             # both items reference it
    assert second.meta["dedup_of"] == first.item_id
    assert first.meta["content_hash"] == second.meta["content_hash"]
    assert library.assets.path_of(second).exists()


def test_different_content_kept_separate(library, tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"AAAA" * 16)
    b.write_bytes(b"BBBB" * 16)
    library.assets.add("A", source=a, kind="image")
    library.assets.add("B", source=b, kind="image")
    assert len(_files(library)) == 2


def test_dedup_can_be_disabled(library, tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(b"PNGDATA" * 16)
    library.assets.add("A", source=a, kind="image")
    library.assets.add("B", source=a, kind="image", dedup=False)
    assert len(_files(library)) == 2             # forced second copy


def test_shared_file_survives_until_last_referrer_removed(library, tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(b"SHARED" * 16)
    first = library.assets.add("A", source=a, kind="image")
    second = library.assets.add("B", source=a, kind="image")
    shared_path = library.assets.path_of(first)

    library.assets.remove(first.item_id)
    assert shared_path.exists()                  # still referenced by B
    library.assets.remove(second.item_id)
    assert not shared_path.exists()              # last referrer gone -> deleted


def test_find_by_hash(library, tmp_path):
    a = tmp_path / "a.png"
    a.write_bytes(b"HASHME" * 16)
    item = library.assets.add("A", source=a, kind="image")
    assert library.assets.find_by_hash(item.meta["content_hash"]).item_id == item.item_id
    assert library.assets.find_by_hash("deadbeef") is None


def test_exports_pool_dedups_identical_renditions(library, tmp_path):
    """Two projects producing an identical export store it once in the pool."""
    export = tmp_path / "reel.mp4"
    export.write_bytes(b"MP4CONTENT" * 32)
    library.exports.add("proj1 reel", source=export, kind="export")
    library.exports.add("proj2 reel", source=export, kind="export")
    files_dir = library.exports.dir / "files"
    assert len(list(files_dir.iterdir())) == 1
