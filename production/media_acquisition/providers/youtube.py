"""YouTube provider (yt-dlp).

Enumerates the channel's Videos + Shorts tabs and downloads at highest quality.
Community posts aren't in those tabs (so they're skipped); live/upcoming streams
are filtered by ``live_status``; deleted/private videos never appear in the
listing. yt-dlp is imported lazily so the module works without it installed.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..models import DownloadResult, MediaItem, Platform
from .base import MediaProvider


def _fmt_date(yyyymmdd: str) -> str:
    if yyyymmdd and len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return ""


class YouTubeProvider(MediaProvider):
    platform = Platform.YOUTUBE

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def is_available(self) -> bool:
        try:
            import yt_dlp  # noqa: F401
            return True
        except Exception:
            return False

    def list_items(self, limit: Optional[int] = None) -> List[MediaItem]:
        import yt_dlp

        base = self.cfg.youtube_channel.rstrip("/")
        items: List[MediaItem] = []
        seen = set()
        opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
                "skip_download": True}
        for tab, kind in ((f"{base}/videos", "long_form"), (f"{base}/shorts", "short")):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(tab, download=False)
            except Exception:
                continue
            for e in (info or {}).get("entries") or []:
                if not e:
                    continue
                vid = e.get("id")
                if not vid or vid in seen:
                    continue
                live = e.get("live_status")
                if live in ("is_live", "is_upcoming") or e.get("is_live"):
                    continue                       # skip live/upcoming
                seen.add(vid)
                items.append(MediaItem(
                    platform=Platform.YOUTUBE, item_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}",
                    title=e.get("title") or "",
                    duration=float(e.get("duration") or 0.0), kind=kind))
        # Preserve YouTube's channel order (newest first) so --limit N takes the
        # N NEWEST videos (long-form first, then Shorts) — the validate-first flow.
        return items[:limit] if limit is not None else items

    def fetch(self, item: MediaItem, dest_dir: Path) -> DownloadResult:
        import yt_dlp

        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        opts = {
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "format": self.cfg.youtube_format,
            "merge_output_format": self.cfg.merge_format,
            "outtmpl": str(dest_dir / f"{item.item_id}.%(ext)s"),
            "continuedl": True,                    # resume partial downloads
            "retries": self.cfg.retries,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(item.url, download=True)

        req = (info.get("requested_downloads") or [])
        if req and req[0].get("filepath"):
            filename = Path(req[0]["filepath"]).name
        else:
            filename = f"{item.item_id}.{self.cfg.merge_format}"
        resolution = f"{info['height']}p" if info.get("height") else ""
        return DownloadResult(
            filename=filename, checksum="", resolution=resolution,
            fps=float(info.get("fps") or 0.0), codec=info.get("vcodec") or "",
            duration=float(info.get("duration") or item.duration or 0.0),
            thumbnail=info.get("thumbnail") or "",
            description=(info.get("description") or "")[:2000],
            publish_date=_fmt_date(info.get("upload_date") or ""))
