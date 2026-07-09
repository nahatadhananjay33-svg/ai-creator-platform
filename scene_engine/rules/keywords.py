"""Deterministic keyword & pattern tables for scene classification (Phase C7).

The whole classifier is a set of ordered, case-insensitive keyword/regex lookups
— NO language model, NO embeddings, NO network. Keeping the vocabulary in one
place makes the rules auditable and the behaviour perfectly reproducible: the
same sentence always lands in the same scene type. Match helpers normalise
whitespace/case and are substring-based (so "vs." matches inside a sentence).
"""
from __future__ import annotations

import re

#: Call-to-action intent — the strongest signal (checked first).
CTA_KEYWORDS: tuple[str, ...] = (
    "subscribe", "follow me", "follow us", "follow for", "hit follow",
    "like and", "hit like", "smash that", "comment below", "leave a comment",
    "link in bio", "link in the description", "sign up", "check out",
    "click the", "click below", "click the link", "join now", "join the",
    "don't forget to", "make sure to", "share this", "tap the",
)

#: Comparison / contrast language.
COMPARISON_KEYWORDS: tuple[str, ...] = (
    "versus", " vs ", " vs. ", "compared to", "comparison between",
    "on the other hand", "whereas", "better than", "worse than",
    "difference between", "pros and cons", "either", " or the ",
)

#: Data / statistics / chart language.
CHART_KEYWORDS: tuple[str, ...] = (
    "percent", "percentage", "statistics", "statistic", "the data",
    "data shows", "the numbers", "revenue", "growth rate", "grew by",
    "increased by", "decreased by", "market share", "graph", "chart",
    "trend", "quarter over quarter", "year over year",
)

#: Enumerated / list language.
LIST_KEYWORDS: tuple[str, ...] = (
    "first", "firstly", "second", "secondly", "third", "thirdly", "finally",
    "step one", "step two", "step three", "here are", "top tips", "top three",
    "three ways", "five ways", "steps to", "reasons why", "the following",
)

#: Quotation language (also see :func:`is_quote` for literal quoted spans).
QUOTE_KEYWORDS: tuple[str, ...] = (
    "once said", "in the words of", "famously said", "as the saying goes",
    "quote,", "quote:", "to quote",
)

#: Video-insert language.
VIDEO_KEYWORDS: tuple[str, ...] = (
    "watch this", "watch how", "here is some footage", "here's some footage",
    "this clip", "roll the", "in this video", "see it in action",
    "play the video", "the footage",
)

#: Still-image insert language.
IMAGE_KEYWORDS: tuple[str, ...] = (
    "look at this", "take a look", "picture this", "here is a photo",
    "here's a photo", "this image", "this picture", "as you can see",
    "shown here", "check this out", "imagine a",
)

#: Map / geography language (an image-insert refinement).
MAP_KEYWORDS: tuple[str, ...] = (
    "on the map", "located in", "the region of", "across the country",
    "around the world", "map of", "in the north", "in the south",
)

#: Screenshot / UI language (an image-insert refinement).
SCREENSHOT_KEYWORDS: tuple[str, ...] = (
    "on the screen", "screenshot", "on your screen", "the dashboard",
    "the app", "the website", "user interface", "the settings",
)

#: Document / report language (an image-insert refinement).
DOCUMENT_KEYWORDS: tuple[str, ...] = (
    "the report", "the document", "the study", "the paper", "the contract",
    "according to the", "the whitepaper", "the article",
)

#: Statistic pattern: a number optionally followed by %, or a large magnitude.
_STAT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b\d[\d,]*\s?(?:percent|million|billion|thousand)\b",
                      re.IGNORECASE)
#: Bullet / enumeration line markers at the start of a sentence.
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[a-e][.)])\s+")
#: A quoted span of at least three words (curly or straight quotes).
_QUOTE_SPAN_RE = re.compile(r"[\"“”'‘’](?:\S+\s+){2,}\S+[\"“”'‘’]")


def _norm(text: str) -> str:
    """Lowercase and collapse whitespace so substring matches are stable."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    """True if any keyword appears in ``text`` (case/space-insensitive)."""
    t = f" {_norm(text)} "
    return any(k in t for k in keywords)


def has_statistic(text: str) -> bool:
    """True if the text carries a numeric statistic (``42%``, ``3 million``)."""
    return bool(_STAT_RE.search(text))


def is_bullet(text: str) -> bool:
    """True if the sentence begins with a bullet/enumeration marker."""
    return bool(_BULLET_RE.match(text))


def is_quote(text: str) -> bool:
    """True if the text is/contains a quoted span of 3+ words or quote wording."""
    return bool(_QUOTE_SPAN_RE.search(text)) or contains_any(text, QUOTE_KEYWORDS)
