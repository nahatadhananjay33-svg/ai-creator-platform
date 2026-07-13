"""Download engine + CLI entry point.

The engine is provider-agnostic: it handles incremental skipping, duplicate
detection, checksum verification, retries, and logging. Resuming partial files
is delegated to the provider tool (yt-dlp / instaloader continue partial
downloads). Run via ``python -m production.media_acquisition.download``.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Config
from .database import MediaDB
from .models import DownloadResult, MediaItem, MediaRecord, Status
from .providers.base import MediaProvider


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DownloadLog:
    """Append-only download log."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, msg: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"{_now()} {msg}\n")


class DownloadEngine:
    def __init__(self, cfg: Config, db: MediaDB, log: DownloadLog,
                 sleep=time.sleep):
        self.cfg = cfg
        self.db = db
        self.log = log
        self._sleep = sleep

    def _already_have(self, item: MediaItem, dest_dir: Path) -> bool:
        rec = self.db.get(item.platform.value, item.item_id)
        if not rec or rec.get("status") != Status.DOWNLOADED.value:
            return False
        fn = rec.get("filename")
        return bool(fn) and (Path(dest_dir) / fn).exists()

    def process(self, provider: MediaProvider, item: MediaItem, dest_dir: Path) -> str:
        """Return one of: downloaded | skipped | failed."""
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        if self._already_have(item, dest_dir):
            self.log.write(f"SKIP {item.platform.value} {item.item_id} (already downloaded)")
            return "skipped"

        last_err = ""
        for attempt in range(1, self.cfg.retries + 1):
            try:
                result = provider.fetch(item, dest_dir)
                path = dest_dir / result.filename
                if not result.filename or not path.exists():
                    raise RuntimeError("download produced no file")
                checksum = result.checksum or sha256(path)

                dup = self.db.get_by_checksum(checksum)
                if dup and dup.get("item_id") != item.item_id:
                    self.log.write(f"DUP {item.item_id} == {dup.get('item_id')} "
                                   f"(checksum {checksum[:12]}); skipping")
                    return "skipped"

                self.db.upsert(self._record(item, result, checksum, Status.DOWNLOADED))
                self.log.write(f"OK {item.platform.value} {item.item_id} {result.filename}")
                return "downloaded"
            except Exception as e:  # noqa: BLE001 - record and retry
                last_err = str(e)
                self.log.write(f"RETRY {attempt}/{self.cfg.retries} {item.item_id}: {last_err}")
                if attempt < self.cfg.retries and self.cfg.retry_backoff_s > 0:
                    self._sleep(self.cfg.retry_backoff_s * attempt)

        self.db.upsert(self._record(item, None, "", Status.FAILED, note=last_err))
        self.log.write(f"FAIL {item.platform.value} {item.item_id}: {last_err}")
        return "failed"

    def _record(self, item: MediaItem, result: Optional[DownloadResult],
                checksum: str, status: Status, note: str = "") -> MediaRecord:
        r = result
        return MediaRecord(
            id=0, platform=item.platform.value, url=item.url, title=item.title,
            publish_date=item.publish_date,
            duration=(r.duration if r and r.duration else item.duration),
            resolution=(r.resolution if r else ""), fps=(r.fps if r else 0.0),
            checksum=checksum, filename=(r.filename if r else ""),
            status=status.value, download_time=_now(), item_id=item.item_id,
            codec=(r.codec if r else ""), kind=item.kind,
            thumbnail=(r.thumbnail if r else ""),
            description=(r.description if r else note))


def main(argv=None) -> int:
    from .cli import run  # lazy: keeps `-m ...download` light
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
