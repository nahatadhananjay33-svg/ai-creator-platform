"""Content pool tests (Phase C15) — hermetic and deterministic."""
from __future__ import annotations

from content_library import ContentLibrary


def test_add_file_item_copies_and_hashes(library, tmp_path):
    src = tmp_path / "logo.png"
    src.write_bytes(b"PNGDATA" * 8)
    item = library.assets.add("Logo", source=src, kind="image", tags=("brand",))
    assert item.path.startswith("files/") and item.path.endswith(".png")
    assert library.assets.path_of(item).exists()
    assert item.meta["content_hash"]                  # file content hash recorded


def test_add_metadata_only_item(library):
    kit = library.brands.add("Dark Kit", kind="brand_kit",
                             meta={"theme": "dark", "soundtrack": "cinematic"})
    assert kit.path == "" and library.brands.path_of(kit) is None
    assert kit.meta["theme"] == "dark"


def test_pool_search(library):
    library.assets.add("Blue Sky", kind="image", tags=("nature", "sky"))
    library.assets.add("City Map", kind="map", tags=("city",))
    assert [i.name for i in library.assets.search(tag="sky")] == ["Blue Sky"]
    assert [i.name for i in library.assets.search(kind="map")] == ["City Map"]
    assert [i.name for i in library.assets.search(name="blue")] == ["Blue Sky"]


def test_pool_persists_across_reopen(library):
    library.voices.add("Narrator", kind="voice_profile", meta={"model": "mock"})
    reopened = ContentLibrary(library.root)
    assert [i.name for i in reopened.voices.list()] == ["Narrator"]


def test_pool_remove_deletes_file(library, tmp_path):
    src = tmp_path / "clip.wav"
    src.write_bytes(b"RIFF____WAVE")
    item = library.music.add("Bed", source=src, kind="music")
    path = library.music.path_of(item)
    assert path.exists()
    library.music.remove(item.item_id)
    assert not path.exists() and not library.music.has(item.item_id)


def test_all_pools_available(library):
    from content_library.library import POOL_NAMES
    for name in POOL_NAMES:
        assert library.pool(name).name == name
