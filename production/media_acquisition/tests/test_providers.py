"""Provider guards: import cleanly and gate on tools/credentials (no network)."""
from __future__ import annotations

from production.media_acquisition.config import Config
from production.media_acquisition.models import Platform
from production.media_acquisition.providers import InstagramProvider, YouTubeProvider


def test_providers_construct():
    assert YouTubeProvider(Config()).platform == Platform.YOUTUBE
    assert InstagramProvider(Config()).platform == Platform.INSTAGRAM


def test_youtube_availability_matches_tool():
    try:
        import yt_dlp  # noqa: F401
        expected = True
    except Exception:
        expected = False
    assert YouTubeProvider(Config()).is_available() is expected


def test_instagram_requires_credentials(monkeypatch):
    for var in ("INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD", "INSTALOADER_SESSION_FILE"):
        monkeypatch.delenv(var, raising=False)
    # no credentials -> unavailable regardless of whether instaloader is installed
    assert InstagramProvider(Config()).is_available() is False
