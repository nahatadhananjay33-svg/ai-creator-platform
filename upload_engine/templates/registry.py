"""Upload-template registry (Phase C18).

Loads the configuration-driven upload templates from ``templates.yaml`` into
immutable :class:`UploadTemplate` values. A template supplies *presentation* for
one content vertical — a lead emoji, the hashtags to append, and the per-platform
call-to-action lines — so tuning how a vertical reads on social media is a YAML
edit, never a code change. Every template yields the same shape, so the metadata
generator treats all verticals identically.

Each vertical inherits ``defaults`` and overrides only what it cares about;
``hashtags`` are merged (vertical tags first, then the defaults'), every other
field is replaced. An unknown vertical name falls back to ``general``.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

from foundation.config import load_yaml

TEMPLATES_PATH: Path = Path(__file__).resolve().parent / "templates.yaml"

#: The vertical used when a requested template name is unknown or blank.
DEFAULT_TEMPLATE = "general"


@dataclass(frozen=True)
class UploadTemplate:
    """One content-vertical's upload presentation (emoji + hashtags + CTAs)."""

    name: str
    emoji: str
    hashtags: tuple[str, ...]            # vertical tags first, then generic ones
    youtube_cta: str
    instagram_cta: str
    facebook_cta: str
    linkedin_cta: str
    thumbnail_max_words: int
    hashtag_limit: int


def _coerce(name: str, base: dict, over: dict) -> UploadTemplate:
    """Build a template from ``defaults`` (base) + a vertical's overrides."""
    def pick(key, default):
        return over.get(key, base.get(key, default))

    # hashtags merge: vertical's own tags first, then the defaults', deduped.
    merged = list(over.get("hashtags", ())) + list(base.get("hashtags", ()))
    hashtags = tuple(dict.fromkeys(t for t in merged if t))
    return UploadTemplate(
        name=name,
        emoji=str(pick("emoji", "🎬")),
        hashtags=hashtags,
        youtube_cta=str(pick("youtube_cta", "Subscribe for more.")),
        instagram_cta=str(pick("instagram_cta", "Follow for more!")),
        facebook_cta=str(pick("facebook_cta", "Follow our page for more.")),
        linkedin_cta=str(pick("linkedin_cta", "Follow for more insights.")),
        thumbnail_max_words=int(pick("thumbnail_max_words", 4)),
        hashtag_limit=int(pick("hashtag_limit", 15)),
    )


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, UploadTemplate]:
    data = load_yaml(TEMPLATES_PATH) or {}
    defaults = data.get("defaults", {}) or {}
    out: dict[str, UploadTemplate] = {}
    for name, over in (data.get("templates", {}) or {}).items():
        out[name] = _coerce(name, defaults, over or {})
    # Guarantee a general fallback even if the YAML omitted it.
    if DEFAULT_TEMPLATE not in out:
        out[DEFAULT_TEMPLATE] = _coerce(DEFAULT_TEMPLATE, defaults, {})
    return out


def available_templates() -> tuple[str, ...]:
    """The vertical names defined in ``templates.yaml`` (sorted)."""
    return tuple(sorted(_load()))


def get_template(name: str | None) -> UploadTemplate:
    """Return the template for ``name``, falling back to ``general`` when unknown.

    A blank/None name or any vertical not present in the YAML resolves to the
    ``general`` template, so metadata generation never fails on an odd label."""
    templates = _load()
    if name and name in templates:
        return templates[name]
    return templates[DEFAULT_TEMPLATE]
