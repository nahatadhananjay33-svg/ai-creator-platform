"""LongFormYouTubeProvider filtering + checksum verification."""
from __future__ import annotations

from production.longform_validation.provider import LongFormYouTubeProvider
from production.longform_validation.verify import format_verify, verify_checksums
from production.media_acquisition.config import Config
from production.media_acquisition.database import MediaDB
from production.media_acquisition.download import DownloadEngine, DownloadLog
from production.media_acquisition.models import MediaItem, Platform
from production.media_acquisition.tests._fakes import FakeProvider


def _mixed_items():
    def item(i, kind):
        return MediaItem(platform=Platform.YOUTUBE, item_id=i,
                         url=f"https://example/{i}", title=i, kind=kind,
                         duration=600.0 if kind == "long_form" else 30.0)
    return [item("long1", "long_form"), item("short1", "short"),
            item("long2", "long_form"), item("short2", "short"),
            item("long3", "long_form")]


def test_provider_filters_to_long_form_only():
    inner = FakeProvider(Platform.YOUTUBE, _mixed_items())
    prov = LongFormYouTubeProvider(inner=inner)
    ids = [i.item_id for i in prov.list_items()]
    assert ids == ["long1", "long2", "long3"]
    assert all(i.kind == "long_form" for i in prov.list_items())


def test_provider_limit_applies_after_filtering():
    inner = FakeProvider(Platform.YOUTUBE, _mixed_items())
    prov = LongFormYouTubeProvider(inner=inner)
    ids = [i.item_id for i in prov.list_items(limit=2)]
    assert ids == ["long1", "long2"]      # shorts never consume limit slots


def test_provider_delegates_availability_and_fetch(tmp_path):
    inner = FakeProvider(Platform.YOUTUBE, _mixed_items())
    prov = LongFormYouTubeProvider(inner=inner)
    assert prov.is_available()
    res = prov.fetch(prov.list_items()[0], tmp_path)
    assert (tmp_path / res.filename).exists()

    assert not LongFormYouTubeProvider(
        inner=FakeProvider(Platform.YOUTUBE, [], available=False)).is_available()


def test_verify_checksums_detects_missing_and_corrupt(tmp_path):
    items = _mixed_items()
    inner = FakeProvider(Platform.YOUTUBE, items,
                         contents={i.item_id: i.item_id.encode() * 100 for i in items})
    prov = LongFormYouTubeProvider(inner=inner)
    db = MediaDB(tmp_path / "media.sqlite")
    engine = DownloadEngine(Config(retry_backoff_s=0), db, DownloadLog(tmp_path / "dl.log"))
    for it in prov.list_items():
        assert engine.process(prov, it, tmp_path / "media") == "downloaded"

    report = verify_checksums(db, tmp_path / "media")
    assert report.ok and report.verified == 3

    (tmp_path / "media" / "long1.mp4").write_bytes(b"corrupted")
    (tmp_path / "media" / "long2.mp4").unlink()
    report = verify_checksums(db, tmp_path / "media")
    assert not report.ok
    assert report.mismatched == ["long1.mp4"]
    assert report.missing == ["long2.mp4"]
    text = format_verify(report)
    assert "Checksum mismatches: 1" in text and "Missing files      : 1" in text


def test_engine_skips_already_downloaded(tmp_path):
    """Re-running the same download is incremental (STEP 1 skip/resume)."""
    items = _mixed_items()
    inner = FakeProvider(Platform.YOUTUBE, items)
    prov = LongFormYouTubeProvider(inner=inner)
    db = MediaDB(tmp_path / "media.sqlite")
    engine = DownloadEngine(Config(retry_backoff_s=0), db, DownloadLog(tmp_path / "dl.log"))
    dest = tmp_path / "media"
    assert [engine.process(prov, i, dest) for i in prov.list_items()] == ["downloaded"] * 3
    assert [engine.process(prov, i, dest) for i in prov.list_items()] == ["skipped"] * 3
