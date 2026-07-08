"""Subtitle export (Phase C4): SRT, WebVTT, JSON, and Timeline captions.

Pure, deterministic serializers over a frozen :class:`CaptionTrack`:

- **SRT** / **WebVTT** — standard sidecar subtitle formats (one cue per caption
  segment by default; ``word_level=True`` emits one cue per word).
- **JSON** — a self-describing structured export (segments + word timings +
  the style name) for programmatic consumers.
- **Timeline captions** — the IR-native JSON (the exact ``CaptionTrack`` schema,
  via the Timeline serde) so a track round-trips losslessly.

No I/O in the formatters; :func:`write_subtitles` is the one helper that writes
files. Timestamps are rendered from the segments' absolute times, so exports are
always in sync with what the renderer draws.
"""
from __future__ import annotations

import json
from pathlib import Path

from reel_engine.interfaces.types import CaptionSegment, CaptionTrack
from reel_engine.timeline.serde import _caption_track_to_dict


def _fmt_timestamp(seconds: float, millis_sep: str) -> str:
    """``HH:MM:SS<sep>mmm`` — ``,`` for SRT, ``.`` for WebVTT."""
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{millis_sep}{ms:03d}"


def _cues(track: CaptionTrack, word_level: bool) -> list[tuple]:
    """Flatten a track to ``(start_s, end_s, text)`` cues."""
    cues: list[tuple] = []
    if word_level:
        for seg in track.segments:
            for w in seg.words:
                cues.append((w.start_s, w.end_s, w.text))
    else:
        for seg in track.segments:
            cues.append((seg.start_s, seg.end_s, seg.text))
    return cues


def to_srt(track: CaptionTrack, *, word_level: bool = False) -> str:
    """SubRip (.srt). One cue per segment (or per word)."""
    blocks: list[str] = []
    for i, (start, end, text) in enumerate(_cues(track, word_level), start=1):
        blocks.append(
            f"{i}\n"
            f"{_fmt_timestamp(start, ',')} --> {_fmt_timestamp(end, ',')}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def to_webvtt(track: CaptionTrack, *, word_level: bool = False) -> str:
    """WebVTT (.vtt). Includes the ``WEBVTT`` header + numbered cue ids."""
    lines: list[str] = ["WEBVTT", ""]
    for i, (start, end, text) in enumerate(_cues(track, word_level), start=1):
        lines += [
            str(i),
            f"{_fmt_timestamp(start, '.')} --> {_fmt_timestamp(end, '.')}",
            text,
            "",
        ]
    return "\n".join(lines)


def _segment_dict(seg: CaptionSegment) -> dict:
    return {
        "index": seg.index, "text": seg.text,
        "start_s": seg.start_s, "end_s": seg.end_s,
        "words": [{"text": w.text, "start_s": w.start_s, "end_s": w.end_s}
                  for w in seg.words],
    }


def to_json(track: CaptionTrack, *, indent: int | None = 2) -> str:
    """Structured caption JSON (segments + word timings + style name)."""
    payload = {
        "track_id": track.track_id,
        "kind": track.kind,
        "style": track.style.name,
        "duration_s": track.duration_s,
        "segments": [_segment_dict(s) for s in track.segments],
    }
    return json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True)


def to_timeline_captions(track: CaptionTrack, *, indent: int | None = 2) -> str:
    """The IR-native CaptionTrack JSON (round-trips via the Timeline serde)."""
    return json.dumps(_caption_track_to_dict(track), ensure_ascii=False,
                      indent=indent, sort_keys=True)


def write_subtitles(
    track: CaptionTrack,
    out_dir: Path | str,
    stem: str = "captions",
    *,
    word_level: bool = False,
) -> dict[str, Path]:
    """Write ``<stem>.srt/.vtt/.json/.captions.json`` and return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "srt": (out_dir / f"{stem}.srt", to_srt(track, word_level=word_level)),
        "vtt": (out_dir / f"{stem}.vtt", to_webvtt(track, word_level=word_level)),
        "json": (out_dir / f"{stem}.json", to_json(track)),
        "timeline": (out_dir / f"{stem}.captions.json", to_timeline_captions(track)),
    }
    paths: dict[str, Path] = {}
    for key, (path, text) in outputs.items():
        path.write_text(text, encoding="utf-8")
        paths[key] = path
    return paths
