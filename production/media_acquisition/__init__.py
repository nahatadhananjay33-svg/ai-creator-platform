"""Production Media Acquisition.

Downloads the creator's OWN YouTube + Instagram video content to a local media
library, then hands off to the Voice Dataset Builder. Authenticates with the
creator's own account where a platform requires it and only fetches content the
account is authorized to access. Uses standard tools (yt-dlp / instaloader);
nothing here bypasses platform protections or terms.

Independent of the Voice Dataset Builder — it only invokes that builder's public
entry point after downloads complete.

Entry point: ``python -m production.media_acquisition.download``.
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
