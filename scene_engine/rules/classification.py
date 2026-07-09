"""Deterministic scene classification (Phase C7).

Assigns each scene a :class:`SceneType` from its narration text and position —
using ONLY the ordered keyword/pattern rules in :mod:`keywords`. No model, no
randomness: the same (text, index, n_scenes) always yields the same type.

Precedence (first match wins) — content intent generally beats position, but the
opening line is the hook and the closing line the outro when nothing stronger
fires:

    1. call-to-action  (strongest explicit intent)
    2. HOOK            (the first scene, unless it was a pure CTA)
    3. quote
    4. comparison
    5. chart / data
    6. bullet list
    7. video insert
    8. image insert    (image / map / screenshot / document)
    9. OUTRO           (the last scene)
   10. explanation / talking-head  (by length — the default)
"""
from __future__ import annotations

from scene_engine.rules import keywords as kw
from scene_engine.storyboard.types import SceneType


def classify_scene(
    text: str,
    *,
    index: int,
    n_scenes: int,
    word_count: int,
    explanation_min_words: int = 24,
) -> SceneType:
    """Classify one scene deterministically. See module docstring for precedence."""
    t = text or ""

    # 1. Explicit call-to-action wins outright.
    if kw.contains_any(t, kw.CTA_KEYWORDS):
        return SceneType.CALL_TO_ACTION

    # 2. The opening beat is the hook (unless it was a CTA, handled above).
    if index == 0:
        return SceneType.HOOK

    # 3-8. Content-driven visual intent, strongest first.
    if kw.is_quote(t):
        return SceneType.QUOTE
    if kw.contains_any(t, kw.COMPARISON_KEYWORDS):
        return SceneType.COMPARISON
    if kw.contains_any(t, kw.CHART_KEYWORDS) or kw.has_statistic(t):
        return SceneType.CHART
    if kw.is_bullet(t) or kw.contains_any(t, kw.LIST_KEYWORDS):
        return SceneType.BULLET_LIST
    if kw.contains_any(t, kw.VIDEO_KEYWORDS):
        return SceneType.VIDEO_INSERT
    if kw.contains_any(t, kw.IMAGE_KEYWORDS + kw.MAP_KEYWORDS
                       + kw.SCREENSHOT_KEYWORDS + kw.DOCUMENT_KEYWORDS):
        return SceneType.IMAGE_INSERT

    # 9. The closing beat is the outro when nothing stronger fired.
    if index == n_scenes - 1:
        return SceneType.OUTRO

    # 10. Default: a longer beat explains; a short one is a talking head.
    return (SceneType.EXPLANATION if word_count >= explanation_min_words
            else SceneType.TALKING_HEAD)


def refine_asset_kind(default_kind: str, text: str) -> str:
    """Narrow a generic ``image`` asset request by keyword.

    An image-insert scene may really want a map, a screenshot, or a document
    still; the finer kind gives the Asset Engine a better later hint. Non-image
    defaults (``chart``, ``video``) pass through unchanged.
    """
    if default_kind != "image":
        return default_kind
    if kw.contains_any(text, kw.MAP_KEYWORDS):
        return "map"
    if kw.contains_any(text, kw.SCREENSHOT_KEYWORDS):
        return "screenshot"
    if kw.contains_any(text, kw.DOCUMENT_KEYWORDS):
        return "document"
    return "image"


def asset_hint(text: str, kind: str, *, max_words: int = 6) -> str:
    """A short, deterministic keyword hint for an asset slot.

    Not AI: the first few salient words of the narration (stopwords dropped),
    prefixed with the kind — enough for the Asset Engine to later search/generate
    without inventing anything here.
    """
    words = [w.strip(".,:;!?\"'()[]").lower() for w in text.split()]
    salient = [w for w in words if w and w not in _STOPWORDS]
    phrase = " ".join(salient[:max_words])
    return f"{kind}: {phrase}".strip().rstrip(":") if phrase else kind


#: A tiny, fixed stopword set (deterministic; not language modelling).
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "is", "are", "was", "were", "be", "this", "that", "these", "those",
    "it", "its", "as", "by", "from", "so", "we", "you", "i", "our", "your",
    "here", "there", "now", "then", "look", "see",
})
