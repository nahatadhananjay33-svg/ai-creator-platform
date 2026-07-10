"""Deterministic metadata generators (Phase C18).

Turn a :class:`ReelSummary` (the reel's own words) plus an
:class:`~upload_engine.templates.registry.UploadTemplate` (per-vertical
presentation) into the eight upload-ready outputs. Every function is pure and
deterministic — no AI, no network, no clocks — and every output has a fallback so
none can come out empty.
"""
from __future__ import annotations

from foundation.shared_utils.text import slugify

from upload_engine.assistant.config import UploadConfig
from upload_engine.assistant.metadata import UploadMetadata
from upload_engine.assistant.summary import ReelSummary
from upload_engine.assistant.text import (
    build_hashtags,
    clamp,
    collapse_ws,
    thumbnail_text,
)
from upload_engine.templates.registry import UploadTemplate, get_template


def _join_blocks(*blocks: str) -> str:
    """Join non-empty blocks with a blank line between them."""
    return "\n\n".join(b for b in (b.strip() for b in blocks) if b)


def _body(summary: ReelSummary, n: int) -> str:
    """The first ``n`` narration lines as a block (falls back to hook/topic)."""
    lines = list(summary.narration[:n])
    if not lines:
        fallback = summary.hook or summary.topic
        lines = [fallback] if fallback else []
    return "\n".join(lines)


def _hook_line(summary: ReelSummary) -> str:
    """The reel's hook, falling back to the first narration line, then the topic."""
    return summary.hook or (summary.narration[0] if summary.narration else "") \
        or summary.topic or "Watch this reel."


def youtube_title(summary: ReelSummary, config: UploadConfig) -> str:
    base = collapse_ws(summary.title or summary.topic) or "Untitled Reel"
    return clamp(base, config.youtube_title_max)


def youtube_description(summary: ReelSummary, template: UploadTemplate,
                        config: UploadConfig, hashtags: tuple[str, ...]) -> str:
    return _join_blocks(
        _hook_line(summary),
        _body(summary, config.description_body_lines),
        template.youtube_cta,
        " ".join(hashtags),
    )


def instagram_caption(summary: ReelSummary, template: UploadTemplate,
                      config: UploadConfig, hashtags: tuple[str, ...]) -> str:
    caption = _join_blocks(
        f"{template.emoji} {_hook_line(summary)}".strip(),
        _body(summary, config.caption_body_lines),
        template.instagram_cta,
        " ".join(hashtags),
    )
    return clamp(caption, config.instagram_caption_max)


def facebook_caption(summary: ReelSummary, template: UploadTemplate,
                     config: UploadConfig, hashtags: tuple[str, ...]) -> str:
    return _join_blocks(
        _hook_line(summary),
        _body(summary, config.caption_body_lines),
        template.facebook_cta,
        " ".join(hashtags[:config.facebook_hashtag_max]),
    )


def linkedin_post(summary: ReelSummary, template: UploadTemplate,
                  config: UploadConfig, hashtags: tuple[str, ...]) -> str:
    takeaways = summary.narration[:config.description_body_lines]
    bullets = "\n".join(f"• {line}" for line in takeaways)
    body = f"Key takeaways:\n{bullets}" if bullets else _body(summary, config.caption_body_lines)
    return _join_blocks(
        _hook_line(summary),
        body,
        template.linkedin_cta,
        " ".join(hashtags[:config.linkedin_hashtag_max]),
    )


def suggested_filename(summary: ReelSummary, config: UploadConfig) -> str:
    slug = slugify(summary.title or summary.prompt or "reel", config.filename_max)
    return f"{slug or 'reel'}.mp4"


def generate_metadata(summary: ReelSummary, *, template: UploadTemplate | str | None = None,
                      config: UploadConfig | None = None) -> UploadMetadata:
    """Generate all eight upload outputs from a reel summary + a template.

    ``template`` may be an :class:`UploadTemplate`, a vertical name, or ``None``
    (in which case the summary's own ``template`` is used, falling back to
    ``general``)."""
    config = config or UploadConfig()
    if not isinstance(template, UploadTemplate):
        template = get_template(template or summary.template)

    hashtags = build_hashtags(summary.keywords, template.hashtags,
                              limit=template.hashtag_limit)
    return UploadMetadata(
        youtube_title=youtube_title(summary, config),
        youtube_description=youtube_description(summary, template, config, hashtags),
        instagram_caption=instagram_caption(summary, template, config, hashtags),
        facebook_caption=facebook_caption(summary, template, config, hashtags),
        linkedin_post=linkedin_post(summary, template, config, hashtags),
        hashtags=hashtags,
        thumbnail_text=thumbnail_text(summary.title, summary.hook,
                                      max_words=template.thumbnail_max_words,
                                      fallback=config.thumbnail_fallback),
        suggested_filename=suggested_filename(summary, config),
        template=template.name,
        source_title=summary.title,
        duration_s=summary.duration_s,
        aspect=summary.aspect,
    )
