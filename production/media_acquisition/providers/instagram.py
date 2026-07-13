"""Instagram provider (instaloader).

Downloads Reels and single video posts from the creator's OWN profile, using the
creator's own authenticated session. Skips images, carousels (sidecar), stories,
and any post without a video. instaloader is imported lazily; the provider is
only "available" when instaloader is installed AND a session/credentials are
provided via environment:

    INSTALOADER_SESSION_FILE + INSTAGRAM_USERNAME   (preferred), or
    INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD

Instagram support is best-effort and may need minor adjustment for the installed
instaloader version; the pipeline core does not depend on it.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..models import DownloadResult, MediaItem, Platform
from .base import MediaProvider


class InstagramProvider(MediaProvider):
    platform = Platform.INSTAGRAM

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def is_available(self) -> bool:
        try:
            import instaloader  # noqa: F401
        except Exception:
            return False
        has_session = os.environ.get("INSTALOADER_SESSION_FILE") and os.environ.get("INSTAGRAM_USERNAME")
        has_login = os.environ.get("INSTAGRAM_USERNAME") and os.environ.get("INSTAGRAM_PASSWORD")
        return bool(has_session or has_login)

    def _loader(self):
        import instaloader
        L = instaloader.Instaloader(
            quiet=True, download_pictures=False, download_videos=True,
            download_video_thumbnails=False, download_geotags=False,
            download_comments=False, save_metadata=False, compress_json=False,
            post_metadata_txt_pattern="")
        user = os.environ.get("INSTAGRAM_USERNAME")
        sess = os.environ.get("INSTALOADER_SESSION_FILE")
        if sess and user:
            L.load_session_from_file(user, sess)
        elif user and os.environ.get("INSTAGRAM_PASSWORD"):
            L.login(user, os.environ["INSTAGRAM_PASSWORD"])
        return L

    def list_items(self, limit: Optional[int] = None) -> List[MediaItem]:
        import instaloader

        L = self._loader()
        profile = instaloader.Profile.from_username(L.context, self.cfg.instagram_profile)
        items: List[MediaItem] = []
        for post in profile.get_posts():
            if getattr(post, "typename", "") == "GraphSidecar":
                continue                            # skip carousels
            if not post.is_video:
                continue                            # skip images
            sc = post.shortcode
            date = post.date_utc.strftime("%Y-%m-%d") if getattr(post, "date_utc", None) else ""
            kind = "reel" if getattr(post, "is_reel", False) else "video_post"
            items.append(MediaItem(
                platform=Platform.INSTAGRAM, item_id=sc,
                url=f"https://www.instagram.com/p/{sc}/",
                title=(getattr(post, "title", "") or "")[:200], publish_date=date,
                duration=float(getattr(post, "video_duration", 0.0) or 0.0), kind=kind,
                extra={"caption": (post.caption or "")[:2000]}))
            if limit is not None and len(items) >= limit:
                break
        return items

    def fetch(self, item: MediaItem, dest_dir: Path) -> DownloadResult:
        import instaloader

        L = self._loader()
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        post = instaloader.Post.from_shortcode(L.context, item.item_id)
        if not post.is_video or not post.video_url:
            raise RuntimeError(f"{item.item_id} has no video")

        filename = f"{item.item_id}.mp4"
        target = dest_dir / filename
        # stream via the authenticated session so signed URLs resolve
        resp = L.context._session.get(post.video_url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                if chunk:
                    f.write(chunk)

        dims = getattr(post, "dimensions", None)
        resolution = f"{dims[0]}p" if dims else ""
        date = post.date_utc.strftime("%Y-%m-%d") if getattr(post, "date_utc", None) else ""
        return DownloadResult(
            filename=filename, checksum="", resolution=resolution, fps=0.0, codec="h264",
            duration=float(getattr(post, "video_duration", 0.0) or item.duration or 0.0),
            description=(post.caption or "")[:2000], publish_date=date)
