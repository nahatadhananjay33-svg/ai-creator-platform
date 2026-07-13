"""Run summary (the final report printed by the CLI)."""
from __future__ import annotations

from typing import List

from .models import Record

_RANK = {"poor": 0, "fair": 1, "good": 2, "excellent": 3}
_LABEL = {0: "poor", 1: "fair", 2: "good", 3: "excellent"}


def summarize(records: List[Record]) -> dict:
    total = len(records)
    accepted = [r for r in records if r.accepted]
    speech_seconds = sum(r.speech_duration for r in accepted)
    if accepted:
        avg_rank = sum(_RANK.get(r.quality, 0) for r in accepted) / len(accepted)
        avg_quality = _LABEL[int(round(avg_rank))]
    else:
        avg_rank, avg_quality = 0.0, "n/a"
    return {
        "total": total,
        "accepted": len(accepted),
        "rejected": total - len(accepted),
        "speech_hours": round(speech_seconds / 3600.0, 3),
        "average_quality": avg_quality,
        "average_quality_rank": round(avg_rank, 2),
    }


def format_summary(records: List[Record]) -> str:
    s = summarize(records)
    return "\n".join([
        "=" * 44,
        "  Voice Dataset Summary",
        "=" * 44,
        f"  Total videos    : {s['total']}",
        f"  Accepted        : {s['accepted']}",
        f"  Rejected        : {s['rejected']}",
        f"  Speech hours    : {s['speech_hours']:.3f}",
        f"  Average quality : {s['average_quality']}",
        "=" * 44,
    ])
