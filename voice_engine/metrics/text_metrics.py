"""Text-side metrics: script coverage and code-switching structure."""
from __future__ import annotations

from foundation.constants.languages import SCRIPT_RANGES


def _char_script(ch: str) -> str | None:
    cp = ord(ch)
    for script, ranges in SCRIPT_RANGES.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


def script_coverage(text: str) -> dict[str, float]:
    """Fraction of script-bearing characters per script (ignores punctuation/space)."""
    counts: dict[str, int] = {}
    total = 0
    for ch in text:
        script = _char_script(ch)
        if script is not None:
            counts[script] = counts.get(script, 0) + 1
            total += 1
    if total == 0:
        return {}
    return {script: round(c / total, 4) for script, c in counts.items()}


def code_switch_segments(text: str) -> int:
    """Number of contiguous same-script segments (1 = monoscript text).

    A proxy for code-switch density used to weight Hinglish/Benglish prompts:
    more segments = more switch points the model must survive.
    """
    segments = 0
    previous: str | None = None
    for ch in text:
        script = _char_script(ch)
        if script is None:
            continue
        if script != previous:
            segments += 1
            previous = script
    return segments
