"""Upload Assistant configuration (Phase C18) — platform limits & knobs.

Small, frozen thresholds the generator honours so its output fits each platform's
practical limits. Defaults are the common real-world caps (YouTube title ≤ 100
chars, Instagram caption ≤ 2200). Everything here is deterministic — no clocks, no
randomness — so the same reel always yields the same metadata.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadConfig:
    """Thresholds that shape the generated upload metadata."""

    youtube_title_max: int = 100        # YouTube hard title limit
    instagram_caption_max: int = 2200   # Instagram caption limit
    filename_max: int = 80              # keep suggested filenames short & safe
    description_body_lines: int = 6     # narration lines folded into a description
    caption_body_lines: int = 3         # narration lines folded into a caption
    facebook_hashtag_max: int = 5       # FB reads better with a few tags
    linkedin_hashtag_max: int = 5       # LinkedIn likewise
    thumbnail_fallback: str = "WATCH NOW"   # used only when no words can be mined

    def __post_init__(self) -> None:
        if self.youtube_title_max <= 0 or self.instagram_caption_max <= 0:
            raise ValueError("caption/title limits must be positive")
        if self.filename_max <= 0:
            raise ValueError("filename_max must be positive")
        if self.description_body_lines < 0 or self.caption_body_lines < 0:
            raise ValueError("body line counts must be >= 0")
        if self.facebook_hashtag_max < 0 or self.linkedin_hashtag_max < 0:
            raise ValueError("hashtag caps must be >= 0")
        if not self.thumbnail_fallback.strip():
            raise ValueError("thumbnail_fallback must be non-empty")
