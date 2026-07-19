"""Reports, artifacts, and visual comparisons for the recovery audit."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .config import SRC_ACCEPTED, VARIANT_ROOT

V2 = VARIANT_ROOT[1280]
V3 = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_v3_recovered")


def _hms(s):
    s = int(round(s))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _mid_frame(path: Path, idx: int | None = None):
    cap = cv2.VideoCapture(str(path))
    nf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx if idx is not None else nf // 2)
    ok, fr = cap.read()
    cap.release()
    return fr if ok else None


def _sheet(rec: dict, dest: Path):
    """original rejected -> old crop -> new crop box -> recovered -> decision."""
    stem = rec["clip"]
    P = 400
    panels, labels = [], []

    src_fr = _mid_frame(SRC_ACCEPTED / rec["source"], rec.get("mid_frame_abs"))
    if src_fr is None:
        return
    panels.append(cv2.resize(src_fr, (int(P * src_fr.shape[1] / src_fr.shape[0]), P)))
    labels.append("original (rejected)")

    old = _mid_frame(V2 / "rejected" / f"{stem}.mp4")
    panels.append(cv2.resize(old, (P, P)) if old is not None
                  else np.zeros((P, P, 3), np.uint8))
    labels.append("old crop (v2)")

    boxed = src_fr.copy()
    if rec.get("mid_box"):
        bx, by, bs = rec["mid_box"]
        cv2.rectangle(boxed, (int(bx), int(by)), (int(bx + bs), int(by + bs)),
                      (0, 128, 255), max(3, src_fr.shape[0] // 250))
    panels.append(cv2.resize(boxed, (int(P * boxed.shape[1] / boxed.shape[0]), P)))
    labels.append("new crop box")

    newf = _mid_frame(V3 / "accepted" / f"{stem}.mp4")
    panels.append(cv2.resize(newf, (P, P)) if newf is not None
                  else np.zeros((P, P, 3), np.uint8))
    labels.append("recovered output")

    gap = np.full((P, 8, 3), 255, np.uint8)
    parts = []
    for i, p in enumerate(panels):
        parts.append(p)
        if i < len(panels) - 1:
            parts.append(gap)
    sheet = cv2.hconcat(parts)
    x = 10
    for p, lab in zip(panels, labels):
        cv2.putText(sheet, lab, (x, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                    (0, 0, 255), 2)
        x += p.shape[1] + 8

    nm = rec.get("new_metrics") or {}
    footer = np.full((92, sheet.shape[1], 3), 20, np.uint8)
    lines = [
        f"was: {rec['original_reason']}   actual: {rec.get('classification', '')}"
        f"   method: {rec['method']} ({rec['confidence']})",
        f"recovered: face {nm.get('face_avg', 0):.0f}px  completeness "
        f"{nm.get('completeness', 0):.3f}  blur {nm.get('blur_var', 0):.0f}"
        f"   DECISION: PROMOTED",
    ]
    for i, txt in enumerate(lines):
        cv2.putText(footer, txt, (12, 34 + i * 34), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(dest), cv2.vconcat([sheet, footer]),
                [cv2.IMWRITE_JPEG_QUALITY, 88])


MODEL_NOTES = [
    ("MuseTalk", "every promoted clip clears its 200px min-face gate; extra "
                 "minutes directly extend the >=6.4s training pool"),
    ("LatentSync", "stable square portrait crops enlarge its affine-aligned "
                   "face region; recovered clips add sync-training variety"),
    ("EchoMimic", "head+shoulders framing matches its conditioning region; "
                  "more pose variety from recovered mid-shots"),
    ("Hallo2", "consistent hair/shoulder margins support its portrait masks; "
               "longer total duration reduces identity drift"),
]


def write_all(results: list[dict], rej_df: pd.DataFrame) -> None:
    rows = []
    for rec in results:
        base = rej_df[rej_df["clip"] == rec["clip"]].iloc[0].to_dict()
        nm = rec.get("new_metrics") or {}
        insp = rec.get("inspection") or {}
        rows.append({
            "clip": rec["clip"], "source": rec["source"],
            "original_reason": rec["original_reason"],
            "classification": rec.get("classification", ""),
            "recovered": bool(rec.get("recovered")),
            "method": rec.get("method", ""),
            "confidence": rec.get("confidence", ""),
            "orig_face_avg": base["face_avg"], "orig_blur": base["blur_var"],
            "orig_completeness": base["completeness"],
            "new_face_avg": nm.get("face_avg"), "new_face_min": nm.get("face_min"),
            "new_blur": nm.get("blur_var"),
            "new_completeness": nm.get("completeness"),
            "new_jitter": nm.get("center_jitter"),
            "new_yaw": nm.get("yaw_abs_mean"), "new_pitch": nm.get("pitch_abs_mean"),
            "new_roll": nm.get("roll_abs_mean"),
            "new_frames": nm.get("frames"), "new_fps": nm.get("fps"),
            "hair_coverage": nm.get("hair_margin"),
            "shoulder_coverage": nm.get("shoulder_margin"),
            "detect_conf": insp.get("detect_conf_mean"),
            "detect_frac": insp.get("detect_frac"),
            "face_roi_blur": insp.get("face_roi_blur_mean"),
            "brightness": insp.get("brightness_mean"),
            "overexposed_frac": insp.get("overexposed_frac"),
            "underexposed_frac": insp.get("underexposed_frac"),
            "camera_shake": insp.get("camera_shake"),
            "audio_mean_db": insp.get("audio_mean_db"),
            "segment": json.dumps(rec.get("segment")) if rec.get("segment") else "",
            "notes": rec.get("notes", ""),
        })
    df = pd.DataFrame(rows).sort_values(["recovered", "clip"],
                                        ascending=[False, True])
    df.to_csv(V3 / "dataset.csv", index=False)
    df.to_excel(V3 / "dataset.xlsx", index=False)
    with sqlite3.connect(V3 / "dataset.sqlite") as db:
        df.to_sql("recovery_audit", db, if_exists="replace", index=False)

    rec_df = df[df.recovered].copy()
    for r in results:
        if r.get("recovered"):
            dest = V3 / "comparison" / f"{r['clip']}.jpg"
            if not dest.exists():
                _sheet(r, dest)

    rec_dur = float((rec_df.new_frames.fillna(0)
                     / rec_df.new_fps.fillna(25).clip(lower=1)).sum())
    rec_frames = int(rec_df.new_frames.fillna(0).sum())
    rec_size = sum((V3 / "accepted" / f"{c}.mp4").stat().st_size
                   for c in rec_df["clip"]
                   if (V3 / "accepted" / f"{c}.mp4").exists())
    v2stats = json.loads(
        (Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_v2")
         / "dataset_duration_statistics.json").read_text(encoding="utf-8"))
    face_gain = (rec_df.new_face_avg - rec_df.orig_face_avg).mean() \
        if len(rec_df) else 0.0
    compl_gain = (rec_df.new_completeness - rec_df.orig_completeness).mean() \
        if len(rec_df) else 0.0

    # ---- false_rejection_report.md
    lines = ["# False Rejection Report", "",
             "Every rejected v2 clip re-audited as a fresh candidate "
             "(metrics + direct visual inspection).", "",
             "| Clip | Original reason | Actual classification | Method | Recovered | Confidence |",
             "|---|---|---|---|---|---|"]
    for r in df.itertuples():
        lines.append(f"| {r.clip} | {r.original_reason} | {r.classification} | "
                     f"{r.method} | {'YES' if r.recovered else 'no'} | "
                     f"{r.confidence or '-'} |")
    lines += ["", "## Classification summary", "",
              df.classification.value_counts().to_string()]
    (V3 / "false_rejection_report.md").write_text("\n".join(lines),
                                                  encoding="utf-8")

    # ---- dataset_gain_report.md
    v2_clips = v2stats["accepted_clips"]
    v2_dur = v2stats["accepted_duration_seconds"]
    gain = f"""# Dataset Gain Report - avatar_dataset_v3_recovered

## Recovery outcome
- Original accepted clips (v2): **{v2_clips}** ({_hms(v2_dur)})
- Rejected clips audited: **{len(df)}**
- Recovered clips: **{len(rec_df)}** ({len(rec_df) / max(len(df), 1) * 100:.0f}% of rejects)
- Recovered duration: **{_hms(rec_dur)}**
- Recovered frames: **{rec_frames:,}**
- Recovered storage: **{rec_size / 1e9:.2f} GB**
- Avg face size of recovered clips: **{rec_df.new_face_avg.mean():.0f}px** \
(v2 accepted avg: {v2stats['average_face_size_px']:.0f}px)
- Avg face-measurement improvement: **{face_gain:+.0f}px**
- Avg crop-completeness improvement: **{compl_gain:+.3f}**

## Combined dataset
| | Clips | Duration |
|---|---|---|
| v2 accepted | {v2_clips} | {_hms(v2_dur)} |
| recovered | +{len(rec_df)} | +{_hms(rec_dur)} |
| **combined** | **{v2_clips + len(rec_df)}** | **{_hms(v2_dur + rec_dur)}** |

## Expected impact per model
""" + "\n".join(f"- **{m}**: {note}" for m, note in MODEL_NOTES)
    (V3 / "dataset_gain_report.md").write_text(gain, encoding="utf-8")

    # ---- top 50 recoveries
    if len(rec_df):
        rec_df["improvement"] = (
            (rec_df.new_completeness.fillna(0) - rec_df.orig_completeness) * 100
            + (rec_df.new_blur.fillna(0) - rec_df.orig_blur).clip(lower=0) / 5)
        top = rec_df.sort_values("improvement", ascending=False).head(50)
        lines = ["# Top 50 Recoveries (by quality improvement)", "",
                 "| # | Clip | Was | Now | Method | Face px | Completeness | Conf. |",
                 "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(top.itertuples(), 1):
            lines.append(
                f"| {i} | {r.clip} | {r.original_reason} | {r.classification} | "
                f"{r.method} | {r.new_face_avg:.0f} | "
                f"{r.orig_completeness:.2f}->{r.new_completeness:.2f} | "
                f"{r.confidence} |")
        (V3 / "top50_recoveries.md").write_text("\n".join(lines),
                                                encoding="utf-8")

    print(f"[reports] {len(rec_df)} recovered, {_hms(rec_dur)} recovered "
          f"duration; combined {v2_clips + len(rec_df)} clips "
          f"{_hms(v2_dur + rec_dur)}; reports in {V3}")
