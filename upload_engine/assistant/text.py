"""Deterministic text helpers for the Upload Assistant (Phase C18).

Tiny, pure string utilities the generators share — clamp to a length at a word
boundary, turn phrases into hashtags, and pull a punchy thumbnail line out of a
title/hook. No randomness, no clocks: the same input always yields the same output.
"""
from __future__ import annotations

import re

#: Low-signal words dropped when mining a short thumbnail line from a sentence.
_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "to", "of", "for", "in", "on", "at",
    "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "your", "you", "we", "our",
    "why", "how", "what", "when", "where", "who", "will", "can", "do", "does",
    "here", "there", "about", "into", "than", "then", "so", "if", "not",
})


def collapse_ws(text: str) -> str:
    """Trim and collapse runs of whitespace to single spaces."""
    return re.sub(r"\s+", " ", (text or "").strip())


def clamp(text: str, max_chars: int, *, ellipsis: str = "…") -> str:
    """Trim ``text`` to ``max_chars`` at a word boundary, adding an ellipsis.

    Only the ends are stripped — internal newlines (paragraph blocks) are kept, so
    a multi-line caption stays multi-line. Returns ``text`` unchanged when it
    already fits, and never returns more than ``max_chars`` chars (ellipsis
    counted)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    if max_chars <= len(ellipsis):
        return text[:max_chars]
    budget = max_chars - len(ellipsis)
    cut = text[:budget]
    m = re.search(r"\s\S*$", cut)          # break at the last whitespace
    if m:
        cut = cut[:m.start()].rstrip()
    return (cut or text[:budget]).rstrip() + ellipsis


def hashtagify(phrase: str) -> str:
    """Turn a phrase into a single ``#hashtag`` (alphanumerics only, lowercased).

    ``"Real Estate"`` -> ``"#realestate"``. Returns ``""`` when nothing survives."""
    slug = re.sub(r"[^0-9a-z]+", "", (phrase or "").lower())
    return f"#{slug}" if slug else ""


def build_hashtags(seeds, template_tags, *, limit: int) -> tuple[str, ...]:
    """Ordered, deduped ``#tags`` from mined ``seeds`` then ``template_tags``.

    Seeds (keywords mined from the reel) lead so the tags are topical; the
    template's vertical/generic tags fill the rest. Capped at ``limit``."""
    out: list[str] = []
    seen: set[str] = set()
    for phrase in list(seeds) + list(template_tags):
        tag = hashtagify(phrase)
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
        if len(out) >= limit:
            break
    return tuple(out)


def thumbnail_text(title: str, hook: str, *, max_words: int, fallback: str) -> str:
    """A short, punchy UPPERCASE thumbnail line mined from the title (then hook).

    Drops low-signal words and keeps the first ``max_words`` meaningful ones; falls
    back to the hook, then to ``fallback`` — so the result is never empty."""
    for source in (title, hook):
        words = [w for w in re.findall(r"[0-9A-Za-z']+", source or "")]
        strong = [w for w in words if w.lower() not in _STOPWORDS]
        picked = (strong or words)[:max_words]
        if picked:
            return " ".join(picked).upper()
    return fallback.strip().upper()
