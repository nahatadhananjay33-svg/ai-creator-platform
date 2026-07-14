"""Aggregate reports: totals/averages, diversity, missing-data, readiness, models.

All figures derive from the per-clip Records. The per-model likelihoods and the
diversity setting/time/expression fields are heuristic estimates (see docs).
"""
from __future__ import annotations

from collections import Counter
from typing import List

from .models import Record


def _avg(xs) -> float:
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def _first(reason: str) -> str:
    return reason.split(";")[0].strip() if reason else ""


def build_report(records: List[Record]) -> dict:
    total = len(records)
    acc = [r for r in records if r.accepted]
    rej = [r for r in records if not r.accepted]
    usable_hours = round(sum(r.duration for r in acc) / 3600.0, 3)
    pool = acc or records

    view = Counter(r.face_view for r in pool)
    setting = Counter(r.setting for r in pool)
    tod = Counter(r.time_of_day for r in pool)
    expr = Counter(r.expression for r in pool)
    walking = sum(1 for r in pool if r.walking_pct > 50)

    diversity = {
        "front_facing": view.get("frontal", 0),
        "left_profile": view.get("left_profile", 0),
        "right_profile": view.get("right_profile", 0),
        "walking": walking, "standing": len(pool) - walking,
        "indoor": setting.get("indoor?", 0), "outdoor": setting.get("outdoor?", 0),
        "setting_unknown": setting.get("unknown", 0),
        "morning": tod.get("morning", 0), "afternoon": tod.get("afternoon", 0),
        "evening": tod.get("evening", 0), "night": tod.get("night", 0),
        "smiling": expr.get("smiling", 0), "neutral": expr.get("neutral", 0),
        "talking": expr.get("talking", 0), "laughing": 0,   # not detectable classically
    }

    n_acc = len(acc)
    close_up = sum(1 for r in acc if r.avg_face_size_pct >= 5)
    profiles = diversity["left_profile"] + diversity["right_profile"]
    missing = []
    if profiles < max(5, n_acc * 0.15):
        missing.append("Need more side-profile clips (left/right)")
    if diversity["smiling"] < max(5, n_acc * 0.15):
        missing.append("Need more smiling clips")
    if diversity["talking"] < max(10, n_acc * 0.30):
        missing.append("Need more static talking-to-camera clips")
    if close_up < max(5, n_acc * 0.20):
        missing.append("Need more close-up videos (larger face in frame)")
    if n_acc < 50:
        missing.append(f"Need more accepted clips overall (have {n_acc}, aim >= 50)")
    if usable_hours < 0.5:
        missing.append(f"Need more total footage (have {usable_hours*60:.0f} min, aim >= 30 min)")

    readiness = _readiness(acc, usable_hours, diversity)
    models = _model_likelihoods(acc)

    return {
        "total": total, "accepted": n_acc, "rejected": len(rej),
        "usable_hours": usable_hours, "avg_duration": _avg([r.duration for r in records]),
        "avg_resolution": f"{int(_avg([r.width for r in records]))}x{int(_avg([r.height for r in records]))}",
        "avg_fps": _avg([r.fps for r in records]),
        "avg_face_visibility": _avg([r.face_visibility_pct for r in records]),
        "avg_lighting": _avg([r.lighting_mean for r in records]),
        "avg_stability": _avg([r.camera_stability for r in records]),
        "top_reject_reasons": Counter(_first(r.reject_reason) for r in rej).most_common(6),
        "diversity": diversity, "missing": missing,
        "readiness": readiness, "models": models,
    }


def _readiness(acc: List[Record], usable_hours: float, div: dict) -> int:
    if not acc:
        return 0
    n = len(acc)
    minutes = min(1.0, usable_hours / 1.0)                       # 1h target
    volume = min(1.0, n / 100.0)
    frontal = min(1.0, div["front_facing"] / max(1, n))
    breadth = min(1.0, (min(div["left_profile"] + div["right_profile"], 20) / 20 * 0.5
                        + min(div["smiling"], 20) / 20 * 0.5))
    return int(round(100 * (0.40 * minutes + 0.30 * volume + 0.20 * frontal + 0.10 * breadth)))


def _model_likelihoods(acc: List[Record]) -> dict:
    """Heuristic % likelihood of building a usable talking-head avatar per model."""
    frontal = [r for r in acc if r.face_view == "frontal"]
    n = len(frontal)
    mouth = _avg([r.mouth_visibility_pct for r in frontal]) if frontal else 0.0
    minutes = sum(r.duration for r in frontal) / 60.0
    # base: needs a body of frontal talking-head clips (~50 clips / ~10 min -> strong)
    base = min(100.0, 0.6 * min(100.0, n * 2.0) + 0.4 * min(100.0, minutes * 10.0))

    def pct(x): return int(max(0, min(100, round(x))))
    return {
        "MuseTalk":   pct(base * 0.9 + mouth * 0.1),   # lip-sync: rewards mouth clarity
        "LatentSync": pct(base * 0.95),                # frontal talking + av-sync material
        "EchoMimic":  pct(base * 0.85),                # frontal + expression range
        "Hallo2":     pct(base * 0.80),                # portrait, benefits from longer clips
    }


def format_report(rep: dict) -> str:
    d = rep["diversity"]
    lines = [
        "=" * 60, "  AVATAR DATASET EVALUATION", "=" * 60,
        f"  Total videos        : {rep['total']}",
        f"  Accepted            : {rep['accepted']}",
        f"  Rejected            : {rep['rejected']}",
        f"  Usable hours        : {rep['usable_hours']:.3f}",
        f"  Avg clip duration   : {rep['avg_duration']:.1f} s",
        f"  Avg resolution      : {rep['avg_resolution']}",
        f"  Avg FPS             : {rep['avg_fps']:.1f}",
        f"  Avg face visibility : {rep['avg_face_visibility']:.1f}%",
        f"  Avg lighting        : {rep['avg_lighting']:.0f}/255",
        f"  Avg stability       : {rep['avg_stability']:.2f}",
        "-" * 60, "  DIVERSITY (accepted)",
        f"  Front / Left / Right: {d['front_facing']} / {d['left_profile']} / {d['right_profile']}",
        f"  Standing / Walking  : {d['standing']} / {d['walking']}",
        f"  Indoor / Outdoor / ?: {d['indoor']} / {d['outdoor']} / {d['setting_unknown']}  (low-confidence)",
        f"  Morn/Aft/Eve/Night  : {d['morning']}/{d['afternoon']}/{d['evening']}/{d['night']}  (from metadata)",
        f"  Smiling/Neutral/Talk: {d['smiling']}/{d['neutral']}/{d['talking']}  (laughing: n/a classically)",
        "-" * 60, "  MISSING FOR PRODUCTION-QUALITY AVATAR",
    ]
    lines += [f"    - {m}" for m in rep["missing"]] or ["    (none — dataset looks well-rounded)"]
    lines += ["-" * 60, f"  AVATAR READINESS SCORE : {rep['readiness']}/100",
              "  Model feasibility (heuristic estimate):"]
    for name, v in rep["models"].items():
        lines.append(f"    {name:11}: {v}%")
    if rep["top_reject_reasons"]:
        lines += ["-" * 60, "  Top reject reasons:"]
        for reason, c in rep["top_reject_reasons"]:
            lines.append(f"    - {reason} ({c})")
    lines.append("=" * 60)
    return "\n".join(lines)
