"""Variant scaling, accept/reject decisions, and dataset artifacts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

from .config import RENDER_RES, RESOLUTIONS, RUN


def variant_row(state: dict, res: int) -> dict:
    """Scale intrinsic 1280-render metrics to an export resolution."""
    k = res / RENDER_RES
    row = {
        "clip": state["stem"], "source": state["source"], "resolution": res,
        "frames": state.get("frames", 0), "fps": state.get("fps", 0.0),
        "face_avg": state.get("face_out_avg_1280", 0.0) * k,
        "face_min": state.get("face_out_min_1280", 0.0) * k,
        "face_max": state.get("face_out_max_1280", 0.0) * k,
        "face_src_avg": state.get("face_src_avg", 0.0),
        "center_jitter": state.get("center_jitter", 0.0),
        "blur_var": state.get("blur_var_1280", 0.0) * k * k,
        "brightness": state.get("brightness", 0.0),
        "completeness": state.get("completeness", 0.0),
        "hair_margin": state.get("hair_margin", 0.0),
        "shoulder_margin": state.get("shoulder_margin", 0.0),
        "face_lost_frac": state.get("face_lost_frac", 1.0),
        "pad_frac": state.get("pad_frac", 0.0),
        "yaw_abs_mean": state.get("yaw_abs_mean", 0.0),
        "pitch_abs_mean": state.get("pitch_abs_mean", 0.0),
        "roll_abs_mean": state.get("roll_abs_mean", 0.0),
    }
    row["accepted"], row["reject_reason"] = _decide(state, row)
    return row


def _decide(state: dict, row: dict):
    a = RUN.accept
    if state.get("status") == "failed":
        return False, state.get("reject_reason", "failed")
    reasons = []
    if row["face_avg"] < a.min_avg_face:
        reasons.append("face_too_small")
    if row["face_min"] < a.min_min_face:
        reasons.append("face_min_too_small")
    if row["center_jitter"] > a.max_center_jitter:
        reasons.append("crop_unstable")
    if row["blur_var"] < a.min_blur_var:
        reasons.append("blurry")
    if row["completeness"] < a.min_completeness:
        reasons.append("head_clipped")
    if row["face_lost_frac"] > a.max_face_lost_frac:
        reasons.append("face_lost")
    return (not reasons), (";".join(reasons) if reasons else "")


def write_artifacts(root: Path, rows: list[dict]) -> None:
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values("clip")
    df.to_csv(root / "dataset.csv", index=False)
    df.to_excel(root / "dataset.xlsx", index=False)
    with sqlite3.connect(root / "dataset.sqlite") as db:
        df.to_sql("clips", db, if_exists="replace", index=False)
    acc = df[df.accepted]
    report = {
        "resolution": int(df.resolution.iloc[0]) if len(df) else None,
        "clips_total": int(len(df)),
        "accepted": int(df.accepted.sum()),
        "rejected": int((~df.accepted).sum()),
        "accepted_minutes": float((acc.frames / acc.fps.clip(lower=1)).sum() / 60)
        if len(acc) else 0.0,
        "face_avg_mean": float(acc.face_avg.mean()) if len(acc) else 0.0,
        "face_min_mean": float(acc.face_min.mean()) if len(acc) else 0.0,
        "jitter_mean": float(acc.center_jitter.mean()) if len(acc) else 0.0,
        "reject_reasons": df[~df.accepted].reject_reason.value_counts().to_dict(),
    }
    (root / "dataset_report.json").write_text(json.dumps(report, indent=2),
                                              encoding="utf-8")


def score_variant(root: Path) -> dict:
    return json.loads((root / "dataset_report.json").read_text(encoding="utf-8"))


def pick_winner(scores: dict[int, dict]) -> int:
    """Largest average face size among variants whose stability holds up.

    All variants share crop tracks, so stability is identical; the tradeoff is
    face size (bigger canvas = bigger, but more upscaled) vs. real detail.
    A variant only 'wins' with a larger canvas if it also keeps >= as many
    accepted clips; upscaling beyond source pixels adds no information, so
    prefer the smallest canvas within 2% of the best accepted-count and
    face_avg >= the accept threshold with margin.
    """
    best_acc = max(s["accepted"] for s in scores.values())
    viable = {r: s for r, s in scores.items()
              if s["accepted"] >= 0.98 * best_acc}
    return max(viable, key=lambda r: (viable[r]["face_avg_mean"], -r))
