"""Deterministic scene segmentation (Phase C7).

Turns a finished script into an ordered list of scenes, each a group of whole
sentences — using ONLY rules, never a language model:

  1. **Manual markers** — a line that is just ``---`` / ``===`` / ``[scene]`` /
     ``[[scene]]`` forces a hard scene break (author override).
  2. **Paragraph boundaries** — a blank line separates paragraphs; a scene never
     spans a blank line.
  3. **Sentence boundaries** — sentences (via the shared splitter) are the atomic
     unit; a scene is always a whole number of sentences (never split mid-sentence).
  4. **Max words / max duration** — within a paragraph, sentences accumulate into
     a scene until adding the next would exceed ``max_words_per_scene`` OR the
     estimated speech would exceed ``max_scene_duration_s``; then a new scene
     starts at the sentence boundary.
  5. **Min words merge** — a trailing fragment below ``min_words_per_scene`` is
     merged back into the previous scene so no scene is a stray word or two.

Every step is order-stable, so the same script always yields the same scenes.
"""
from __future__ import annotations

import re

from foundation.shared_utils.text import split_sentences

from scene_engine.config.settings import SceneEngineConfig

#: A line that means "start a new scene here" (author override). The line must be
#: ONLY the marker (optionally with surrounding whitespace).
_MARKER_RE = re.compile(r"^\s*(?:---+|===+|\[\[?\s*scene\s*\]?\]|#{1,6}\s*scene)\s*$",
                        re.IGNORECASE)
_WORD_RE = re.compile(r"\S+")


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def _split_blocks(script: str) -> list[list[str]]:
    """Split the script into blocks separated by manual markers or blank lines.

    Returns a list of blocks; each block is a list of non-empty lines. Markers
    and blank lines are consumed as separators (a marker always forces a break;
    consecutive blank lines collapse to one).
    """
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in script.splitlines():
        line = raw.strip()
        if _MARKER_RE.match(line):
            if current:
                blocks.append(current)
                current = []
            continue
        if not line:                      # blank line -> paragraph boundary
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _estimate_speech_s(word_count: int, wpm: float) -> float:
    return (word_count / wpm) * 60.0 if wpm > 0 else 0.0


def _pack_sentences(sentences: list[str], cfg: SceneEngineConfig) -> list[list[str]]:
    """Greedily pack whole sentences into scenes under the word/duration caps.

    A single sentence that alone exceeds a cap becomes its own scene (we never
    split mid-sentence — rule #3 beats rules #4).
    """
    scenes: list[list[str]] = []
    cur: list[str] = []
    cur_words = 0
    for sent in sentences:
        w = _count_words(sent)
        would_words = cur_words + w
        would_speech = _estimate_speech_s(would_words, cfg.words_per_minute)
        over = (would_words > cfg.max_words_per_scene
                or would_speech > cfg.max_scene_duration_s)
        if cur and over:
            scenes.append(cur)
            cur, cur_words = [], 0
        cur.append(sent)
        cur_words += w
    if cur:
        scenes.append(cur)
    return scenes


def _merge_small_tail(scenes: list[list[str]], cfg: SceneEngineConfig) -> list[list[str]]:
    """Merge any scene below ``min_words_per_scene`` into its neighbour.

    A tiny trailing fragment folds into the previous scene; a tiny leading
    fragment folds into the next. Keeps every emitted scene substantial without
    breaking sentence boundaries.
    """
    if not scenes:
        return scenes
    merged: list[list[str]] = []
    for scene in scenes:
        words = sum(_count_words(s) for s in scene)
        if words < cfg.min_words_per_scene and merged:
            merged[-1].extend(scene)      # fold small fragment into the previous
        else:
            merged.append(list(scene))
    # A tiny FIRST scene has no previous — fold it forward into the second.
    if len(merged) >= 2:
        first_words = sum(_count_words(s) for s in merged[0])
        if first_words < cfg.min_words_per_scene:
            merged[1] = merged[0] + merged[1]
            merged.pop(0)
    return merged


def segment_scenes(script: str, cfg: SceneEngineConfig | None = None) -> list[list[str]]:
    """Segment a script into scenes, each a list of whole sentences.

    Deterministic and pure. Applies, in order: manual markers + paragraph breaks
    (block split) -> sentence split -> word/duration packing -> small-tail merge.
    """
    cfg = cfg or SceneEngineConfig()
    scenes: list[list[str]] = []
    for block in _split_blocks(script):
        text = " ".join(block)
        sentences = split_sentences(text) or ([text] if text.strip() else [])
        if not sentences:
            continue
        scenes.extend(_pack_sentences(sentences, cfg))
    return _merge_small_tail(scenes, cfg)
