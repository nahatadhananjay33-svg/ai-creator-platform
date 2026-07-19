"""Thumbnails, comparison sheets, and the final upgrade report."""
from __future__ import annotations

import json
import random
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .config import (OUT_ROOT, RENDER_DIR, RESOLUTIONS, SRC_ACCEPTED,
                     VARIANT_ROOT, RUN)


def make_thumbnails(states: list[dict], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for st in states:
        if st.get("status") != "rendered":
            continue
        out = dest / f"{st['stem']}.jpg"
        if out.exists():
            continue
        master = RENDER_DIR / f"{st['stem']}.mp4"
        cap = cv2.VideoCapture(str(master))
        cap.set(cv2.CAP_PROP_POS_FRAMES, st.get("mid_frame", 0))
        ok, frame = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(str(out), cv2.resize(frame, (256, 256)),
                        [cv2.IMWRITE_JPEG_QUALITY, 85])


def make_comparison_sheets(states: list[dict], dest: Path, k: int) -> int:
    """Original -> detected face -> crop box -> final crop, one sheet per clip."""
    dest.mkdir(parents=True, exist_ok=True)
    rendered = [s for s in states if s.get("status") == "rendered"]
    random.seed(42)
    sample = random.sample(rendered, min(k, len(rendered)))
    made = 0
    for st in sample:
        out = dest / f"{st['stem']}.jpg"
        if out.exists():
            made += 1
            continue
        src = SRC_ACCEPTED / st["source"]
        cap = cv2.VideoCapture(str(src))
        cap.set(cv2.CAP_PROP_POS_FRAMES, st.get("mid_frame", 0))
        ok, frame = cap.read()
        cap.release()
        if not ok:
            continue
        H, W = frame.shape[:2]
        panel_h = 480
        scale = panel_h / H

        def shrink(img):
            return cv2.resize(img, (int(img.shape[1] * panel_h / img.shape[0]),
                                    panel_h))

        p1 = shrink(frame)
        fx, fy, fw, fh = st["mid_face"]
        p2 = frame.copy()
        cv2.rectangle(p2, (int(fx - fw / 2), int(fy - fh / 2)),
                      (int(fx + fw / 2), int(fy + fh / 2)), (0, 255, 0),
                      max(2, int(4 / scale * scale) * 3))
        p2 = shrink(p2)
        bx, by, bs = st["mid_box"]
        p3 = frame.copy()
        cv2.rectangle(p3, (int(bx), int(by)), (int(bx + bs), int(by + bs)),
                      (0, 128, 255), max(3, int(H / 250)))
        p3 = shrink(p3)
        master = RENDER_DIR / f"{st['stem']}.mp4"
        cap = cv2.VideoCapture(str(master))
        cap.set(cv2.CAP_PROP_POS_FRAMES, st.get("mid_frame", 0))
        ok, crop = cap.read()
        cap.release()
        p4 = cv2.resize(crop, (panel_h, panel_h)) if ok else np.zeros(
            (panel_h, panel_h, 3), np.uint8)
        gap = np.full((panel_h, 8, 3), 255, np.uint8)
        sheet = cv2.hconcat([p1, gap, p2, gap, p3, gap, p4])
        for i, label in enumerate(("original", "detected face", "crop box",
                                   "final crop")):
            cv2.putText(sheet, label, (10 + i * (sheet.shape[1] // 4), 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
        made += 1
    return made


def write_upgrade_report(states: list[dict], scores: dict[int, dict],
                         winner: int, dest: Path) -> None:
    rendered = [s for s in states if s.get("status") == "rendered"]
    before = np.array([s["face_src_avg"] for s in rendered])
    wdf = pd.read_csv(VARIANT_ROOT[winner] / "dataset.csv")
    acc = wdf[wdf.accepted]
    after = acc.face_avg
    improvement = ((after.mean() / before.mean()) - 1) * 100 if len(acc) else 0.0
    gains = sorted(
        ((float(r.face_avg / max(r.face_src_avg, 1)), r.clip)
         for r in acc.itertuples()), reverse=True)
    weak = wdf[~wdf.accepted].reject_reason.value_counts()
    lines = [
        "# Avatar Dataset v2 - Upgrade Report", "",
        f"Source: `{SRC_ACCEPTED}` | Winner variant: **{winner}px**", "",
        "## Totals",
        f"- Videos processed: **{len(states)}**",
        f"- Rendered OK: **{len(rendered)}**"
        f" (failed: {len(states) - len(rendered)})", "",
        "## Variant comparison", "",
        "| Variant | Accepted | Rejected | Avg face (accepted) | Min-face mean | Jitter |",
        "|---|---|---|---|---|---|",
    ]
    for r in RESOLUTIONS:
        s = scores[r]
        mark = " **<- winner**" if r == winner else ""
        lines.append(f"| {r}px{mark} | {s['accepted']} | {s['rejected']} | "
                     f"{s['face_avg_mean']:.0f}px | {s['face_min_mean']:.0f}px | "
                     f"{s['jitter_mean']:.4f} |")
    lines += [
        "",
        "## Face size",
        f"- Average face size before (source frames): **{before.mean():.0f}px**",
        f"- Average face size after (winner accepted): **{after.mean():.0f}px**"
        if len(acc) else "- no accepted clips",
        f"- Improvement: **{improvement:+.0f}%**",
        f"- Largest improvement: {gains[0][1]} ({gains[0][0]:.1f}x)" if gains else "",
        "",
        "## Remaining weak clips (winner variant)",
    ]
    lines += [f"- {reason}: {count}" for reason, count in weak.items()] or ["- none"]
    top = acc.sort_values("face_avg", ascending=False).clip[:20] \
        if len(acc) else []
    lines += [
        "",
        "## Recommended clips for retraining (largest stable faces)",
        *[f"- {c}" for c in top],
        "",
        "## Expected impact per model",
        "- **MuseTalk**: largest gain - its 200px min-face filter rejected most "
        "of v1; accepted v2 clips all clear it by construction.",
        "- **LatentSync**: benefits from the stable square face-centric crops "
        "(its affine face alignment gets a much larger source region).",
        "- **EchoMimic**: head+shoulders framing matches its expected "
        "conditioning region; stability reduces its pose-encoder noise.",
        "- **Hallo2**: profits from consistent hair/shoulder margins for its "
        "portrait-region masks; fewer identity drift artifacts expected.",
    ]
    (dest / "dataset_upgrade_report.md").write_text("\n".join(lines),
                                                    encoding="utf-8")
