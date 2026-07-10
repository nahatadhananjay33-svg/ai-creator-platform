"""The generated upload metadata (Phase C18) — the copy a creator pastes.

:class:`UploadMetadata` is an immutable value holding the eight upload-ready
outputs plus a little provenance. It knows how to serialise itself (``to_dict`` /
``metadata.json``) and how to tell whether any required output came out empty
(``missing_fields`` — the validation hook).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: The eight outputs the Upload Assistant must always produce (the required set).
REQUIRED_FIELDS: tuple[str, ...] = (
    "youtube_title",
    "youtube_description",
    "instagram_caption",
    "facebook_caption",
    "linkedin_post",
    "hashtags",
    "thumbnail_text",
    "suggested_filename",
)


@dataclass(frozen=True)
class UploadMetadata:
    """The eight upload-ready outputs for one reel (+ provenance)."""

    youtube_title: str
    youtube_description: str
    instagram_caption: str
    facebook_caption: str
    linkedin_post: str
    hashtags: tuple[str, ...]
    thumbnail_text: str
    suggested_filename: str
    # ---- provenance (not part of the required output set) --------------------
    template: str = "general"
    source_title: str = ""
    duration_s: float = 0.0
    aspect: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def required(self) -> dict[str, Any]:
        """Just the eight required outputs, keyed by name."""
        return {name: getattr(self, name) for name in REQUIRED_FIELDS}

    def missing_fields(self) -> tuple[str, ...]:
        """Required outputs that came out empty (the validation check).

        A blank string or an empty hashtag tuple counts as missing."""
        missing = []
        for name in REQUIRED_FIELDS:
            value = getattr(self, name)
            empty = (len(value) == 0) if isinstance(value, tuple) else not str(value).strip()
            if empty:
                missing.append(name)
        return tuple(missing)

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields()

    def to_dict(self) -> dict[str, Any]:
        return {
            "youtube_title": self.youtube_title,
            "youtube_description": self.youtube_description,
            "instagram_caption": self.instagram_caption,
            "facebook_caption": self.facebook_caption,
            "linkedin_post": self.linkedin_post,
            "hashtags": list(self.hashtags),
            "thumbnail_text": self.thumbnail_text,
            "suggested_filename": self.suggested_filename,
            "template": self.template,
            "source_title": self.source_title,
            "duration_s": self.duration_s,
            "aspect": self.aspect,
        }
