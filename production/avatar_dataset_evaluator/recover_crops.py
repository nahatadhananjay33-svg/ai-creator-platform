"""Phase A1 - Face Crop Recovery.

Recovers videos rejected for 'face too small': detect the face, crop an
aspect-preserving region around it (so the face becomes large), re-evaluate ONLY
the crops with the EXISTING evaluator, then merge the newly-accepted crops into
the dataset. Reuses production.avatar_dataset_evaluator; trains nothing, does not
touch the Avatar Engine.

    python -m production.avatar_dataset_evaluator.recover_crops
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

from .analyze import _cascade
from .config import Config, Paths
from .pipeline import evaluate_dataset
from .report import build_report
from .storage import load_records, write_csv, write_sqlite, write_xlsx


def find_face_too_small(records) -> list:
    return [r for r in records if not r.accepted and "face too small" in (r.reject_reason or "")]


def detect_face_boxes(video, cfg: Config) -> List[tuple]:
    """Sample frames and return the largest face box per frame (x, y, w, h)."""
    import cv2
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if n <= 0 or h == 0:
        cap.release()
        return []
    front = _cascade("haarcascade_frontalface_default.xml")
    prof = _cascade("haarcascade_profileface.xml")
    minsize = max(16, int(cfg.detect_min_size_frac * h * 0.5))   # smaller -> catch small faces
    boxes = []
    for i in np.linspace(0, max(0, n - 1), cfg.frame_samples).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        d = front.detectMultiScale(g, cfg.detect_scale, cfg.detect_neighbors, minSize=(minsize, minsize))
        if not len(d):
            d = prof.detectMultiScale(g, cfg.detect_scale, cfg.detect_neighbors, minSize=(minsize, minsize))
        if len(d):
            boxes.append(tuple(int(v) for v in max(d, key=lambda b: b[2] * b[3])))
    cap.release()
    return boxes


def compute_crop(w: int, h: int, boxes: List[tuple], target_face_frac: float = 0.32) -> Optional[tuple]:
    """Aspect-preserving crop centered on the (median) face, sized so the face is
    ~``target_face_frac`` of the crop height. Returns (x, y, w, h) or None."""
    if len(boxes) < 3 or w <= 0 or h <= 0:
        return None
    b = np.array(boxes, dtype=float)
    cx = float(np.median(b[:, 0] + b[:, 2] / 2))
    cy = float(np.median(b[:, 1] + b[:, 3] / 2))
    fh = float(np.median(b[:, 3]))
    aspect = w / h
    crop_h = min(float(h), fh / target_face_frac)
    crop_w = crop_h * aspect
    if crop_w > w:
        crop_w = float(w)
        crop_h = crop_w / aspect
    cw = int(crop_w) // 2 * 2
    ch = int(crop_h) // 2 * 2
    if cw >= int(w * 0.95) and ch >= int(h * 0.95):
        return None                                  # can't enlarge -> pointless
    x = max(0, min(int(round(cx - cw / 2)), w - cw))
    y = max(0, min(int(round(cy - ch / 2)), h - ch))
    return (x, y, cw, ch)


def crop_video(video, crop: tuple, out_path: Path) -> bool:
    x, y, w, h = crop
    if Path(out_path).exists():
        return True
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
           "-vf", f"crop={w}:{h}:{x}:{y}", "-c:v", "libx264", "-crf", "18",
           "-preset", "veryfast", "-c:a", "copy", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0 and Path(out_path).exists()


def _progress(it, total, on):
    if not on:
        return it
    try:
        from tqdm.auto import tqdm
        return tqdm(it, total=total, desc="crop", unit="vid")
    except Exception:
        return it


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m production.avatar_dataset_evaluator.recover_crops")
    ap.add_argument("--base", default=None)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    cfg = Config()
    root = Path(args.base) if args.base else cfg.base_dir()
    paths = Paths.make(root).ensure()
    main_db = paths.out / "dataset.sqlite"
    all_records = load_records(main_db)
    old_accepted = sum(1 for r in all_records if r.accepted)

    targets = find_face_too_small(all_records)
    print(f"STEP 1: {len(targets)} videos rejected for 'face too small'")

    crop_dir = paths.out / "cropped_src"
    crop_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for r in _progress(targets, len(targets), True):
        src = paths.source / r.source
        if not src.exists():
            src = paths.rejected / r.filename
        if not src.exists():
            continue
        crop = compute_crop(r.width, r.height, detect_face_boxes(src, cfg))
        if crop is None:
            continue
        out = crop_dir / (Path(r.filename).stem + "_crop.mp4")
        if crop_video(src, crop, out):
            made.append(out)
    print(f"STEP 2: cropped {len(made)} / {len(targets)} "
          f"(rest had no stable face or couldn't be enlarged)")

    # STEP 3: re-evaluate ONLY the cropped videos with the existing evaluator
    rec_paths = Paths(root=paths.out / "_recovery", source=crop_dir).ensure()
    cropped_records = evaluate_dataset(rec_paths, cfg, resume=False, progress=True)
    recovered = [r for r in cropped_records if r.accepted]
    still_rej = [r for r in cropped_records if not r.accepted]
    n_proc = len(cropped_records)

    print("\nSTEP 4:")
    print(f"  Videos processed : {n_proc}")
    print(f"  Recovered        : {len(recovered)}")
    print(f"  Still rejected   : {len(still_rej)}")
    print(f"  Recovery %       : {len(recovered) / max(1, n_proc) * 100:.1f}%")

    # STEP 5: merge recovered crops into the accepted dataset (no duplicates)
    existing = {r.filename for r in all_records}
    merged = list(all_records)
    for r in recovered:
        src = crop_dir / r.filename
        dst = paths.accepted / r.filename
        if src.exists() and not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copyfile(src, dst)
        if r.filename not in existing:
            r.source = f"cropped_src/{r.filename}"
            merged.append(r)
            existing.add(r.filename)
    for i, rr in enumerate(merged, 1):
        rr.id = i
    write_sqlite(merged, main_db)
    write_csv(merged, paths.out / "dataset.csv")
    write_xlsx(merged, paths.out / "dataset.xlsx")

    rep = build_report(merged)
    final_accepted = sum(1 for r in merged if r.accepted)
    print("\nSTEP 6: recovery summary")
    print(f"  Old accepted videos  : {old_accepted}")
    print(f"  New accepted (crops) : {len(recovered)}")
    print(f"  Final accepted videos: {final_accepted}")
    print(f"  Final readiness score: {rep['readiness']}/100")
    (paths.reports / "recovery_report.txt").write_text(
        f"old_accepted={old_accepted}\nnew_accepted={len(recovered)}\n"
        f"final_accepted={final_accepted}\nreadiness={rep['readiness']}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
