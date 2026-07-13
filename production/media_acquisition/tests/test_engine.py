"""Download engine: incremental skip, retry, failure, dedup, manager stats."""
from __future__ import annotations

from production.media_acquisition.config import Config
from production.media_acquisition.database import MediaDB
from production.media_acquisition.download import DownloadEngine, DownloadLog
from production.media_acquisition.manager import run_provider
from production.media_acquisition.models import Platform, Status
from production.media_acquisition.tests._fakes import FakeProvider, make_items

CFG = Config(retries=3, retry_backoff_s=0.0)


def _engine(tmp_path):
    db = MediaDB(tmp_path / "media.sqlite")
    log = DownloadLog(tmp_path / "download.log")
    return DownloadEngine(CFG, db, log, sleep=lambda *_: None), db


def test_download_then_skip(tmp_path):
    engine, db = _engine(tmp_path)
    dest = tmp_path / "youtube"
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["a"]))
    item = prov.list_items()[0]

    assert engine.process(prov, item, dest) == "downloaded"
    assert (dest / "a.mp4").exists()
    # second run: file present + recorded -> skipped (never re-download)
    assert engine.process(prov, item, dest) == "skipped"
    rec = db.get("youtube", "a")
    assert rec["status"] == "downloaded" and rec["checksum"]


def test_retry_then_success(tmp_path):
    engine, db = _engine(tmp_path)
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["b"]),
                        fail_first={"b": 2})   # fail twice, succeed on 3rd
    assert engine.process(prov, prov.list_items()[0], tmp_path / "yt") == "downloaded"


def test_retry_exhausted_fails(tmp_path):
    engine, db = _engine(tmp_path)
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["c"]),
                        fail_first={"c": 99})  # always fails
    assert engine.process(prov, prov.list_items()[0], tmp_path / "yt") == "failed"
    assert db.get("youtube", "c")["status"] == "failed"


def test_duplicate_checksum_skipped(tmp_path):
    engine, db = _engine(tmp_path)
    dest = tmp_path / "yt"
    same = b"identical-bytes"
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["d1", "d2"]),
                        contents={"d1": same, "d2": same})
    items = prov.list_items()
    assert engine.process(prov, items[0], dest) == "downloaded"
    assert engine.process(prov, items[1], dest) == "skipped"   # same checksum


def test_manager_stats(tmp_path):
    engine, db = _engine(tmp_path)
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["x", "y", "z"], duration=3600.0),
                        fail_first={"z": 99})
    stats = run_provider(prov, tmp_path / "yt", engine, CFG)
    assert stats.discovered == 3
    assert stats.downloaded == 2 and stats.failed == 1
    assert abs(stats.hours - 2.0) < 1e-6   # two 3600s files downloaded


def test_unavailable_provider_skipped(tmp_path):
    engine, db = _engine(tmp_path)
    prov = FakeProvider(Platform.INSTAGRAM, make_items(Platform.INSTAGRAM, ["a"]),
                        available=False)
    stats = run_provider(prov, tmp_path / "ig", engine, CFG)
    assert stats.available is False and stats.discovered == 0


def test_limit_applied(tmp_path):
    engine, db = _engine(tmp_path)
    prov = FakeProvider(Platform.YOUTUBE, make_items(Platform.YOUTUBE, ["1", "2", "3", "4", "5"]))
    stats = run_provider(prov, tmp_path / "yt", engine, CFG, limit=2)
    assert stats.discovered == 2 and stats.downloaded == 2
