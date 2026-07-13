"""Media providers (YouTube, Instagram) behind a common interface.

Providers wrap standard tools (yt-dlp, instaloader) and are only *available*
when their tool + any required credentials are present, so the rest of the
pipeline (and the test suite) runs without them.
"""
from .base import MediaProvider
from .instagram import InstagramProvider
from .youtube import YouTubeProvider

__all__ = ["MediaProvider", "YouTubeProvider", "InstagramProvider"]
