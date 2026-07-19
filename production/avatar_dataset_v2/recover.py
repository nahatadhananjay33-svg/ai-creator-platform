"""Production recovery audit over avatar_dataset_v2_1280 rejected clips.

    python -m production.avatar_dataset_v2.recover

Every rejected clip is treated as a fresh candidate: metrics + direct visual
inspection (per-second filmstrip, per-frame confidence/blur/exposure/shake,
audio speaking activity), then recovery attempts (per-frame re-detection at
higher input resolution, tighter smoothing, best-segment extraction). A clip
is promoted ONLY if it passes the ORIGINAL accept thresholds. All prior
datasets are read-only; output goes to avatar_dataset_v3_recovered.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .config import RENDER_RES, RUN, SRC_ACCEPTED, VARIANT_ROOT, safe_stem
from .detect import detect_frame
from .metrics import variant_row
from .render import _ffprobe_fps, _sample_output_quality
from .tracking import interpolate_track, solve_crop

V2 = VARIANT_ROOT[1280]                     # input (read-only)
V3 = Path(r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset_v3_recovered")
V3_STATE = V3 / "reports" / "state"
V3_STRIPS = V3 / "reports" / "inspection"


@dataclass(frozen=True)
class RecoveryCfg:
    detect_stride: int = 1          # every frame (v2 used 2)
    detect_max_dim: int = 1440      # higher detector input res (v2: 960)
    detect_confidence: float = 0.3  # lower floor (v2: 0.4)
    smooth_window_s: float = 0.6    # tighter smoothing follows motion better
    min_segment_s: float = 6.6      # a usable segment must train (>=160f@25)
    blur_resample: int = 16         # denser blur sampling than v2's 8
    strip_thumb: int = 144          # filmstrip thumbnail height


REC = RecoveryCfg()


# ---------------------------------------------------------------- inspection

def _audio_rms(src: Path) -> float:
    """Mean audio level (dB) as a speaking-activity proxy; -91 = silence."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(src), "-map", "0:a:0?",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True)
    for line in out.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0])
            except ValueError:
                pass
    return -91.0


def _detect_and_inspect(src: Path, stem: str):
    """One decode pass: detection track + visual inspection + filmstrip."""
    import mediapipe as mp
    from . import detect as det
    det._detector = mp.solutions.face_detection.FaceDetection(
        model_selection=1, min_detection_confidence=REC.detect_confidence)
    cap = cv2.VideoCapture(str(src))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = _ffprobe_fps(src)
    step_1s = max(1, int(round(fps)))
    samples, n = {}, 0
    confs, blurs, brights, over, under, shakes = [], [], [], [], [], []
    thumbs = []
    prev_small = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        d = detect_frame(frame, REC.detect_max_dim)
        if d is not None:
            samples[n] = d
            confs.append(d["score"])
        small = cv2.resize(frame, (160, int(160 * H / W) or 90))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if n % step_1s == 0 or n == 0:                 # every 1 s + beginning
            thumbs.append(cv2.resize(
                frame, (int(REC.strip_thumb * W / H), REC.strip_thumb)))
            brights.append(float(gray.mean()))
            over.append(float((gray > 245).mean()))
            under.append(float((gray < 10).mean()))
            if d is not None:
                x0 = int(max(0, d["cx"] - d["w"] / 2) * 160 / W)
                x1 = int(min(W, d["cx"] + d["w"] / 2) * 160 / W)
                y0 = int(max(0, d["cy"] - d["h"] / 2) * small.shape[0] / H)
                y1 = int(min(H, d["cy"] + d["h"] / 2) * small.shape[0] / H)
                roi = gray[y0:max(y1, y0 + 2), x0:max(x1, x0 + 2)]
                if roi.size:
                    blurs.append(float(cv2.Laplacian(roi, cv2.CV_64F).var()))
        if prev_small is not None:
            shakes.append(float(np.mean(cv2.absdiff(gray, prev_small))))
        prev_small = gray
        n += 1
    cap.release()

    # middle + end thumbnails guaranteed present
    strip = None
    if thumbs:
        strip = cv2.hconcat([cv2.resize(t, (thumbs[0].shape[1], REC.strip_thumb))
                             for t in thumbs[:24]])
        V3_STRIPS.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(V3_STRIPS / f"{stem}.jpg"), strip,
                    [cv2.IMWRITE_JPEG_QUALITY, 82])

    inspection = {
        "detect_conf_mean": float(np.mean(confs)) if confs else 0.0,
        "detect_frac": len(samples) / max(n, 1),
        "face_roi_blur_mean": float(np.mean(blurs)) if blurs else 0.0,
        "brightness_mean": float(np.mean(brights)) if brights else 0.0,
        "overexposed_frac": float(np.mean(over)) if over else 0.0,
        "underexposed_frac": float(np.mean(under)) if under else 0.0,
        "camera_shake": float(np.mean(shakes)) if shakes else 0.0,
        "audio_mean_db": _audio_rms(src),
        "frames_inspected_1s": len(thumbs),
    }
    return samples, n, W, H, fps, inspection


# ---------------------------------------------------------------- recovery

def _best_segment(good: np.ndarray, min_frames: int):
    best = (0, 0)
    i, n = 0, len(good)
    while i < n:
        if good[i]:
            j = i
            while j < n and good[j]:
                j += 1
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 1
    return best if best[1] - best[0] >= min_frames else None


def _render_range(src: Path, dest: Path, crop, f0: int, f1: int, fps: float):
    xs, ys, sides = crop["x"], crop["y"], crop["side"]
    tmp = dest.with_suffix(".tmp.mp4")
    dest.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{RENDER_RES}x{RENDER_RES}", "-r", f"{fps:.6f}", "-i", "-",
         "-ss", f"{f0 / fps:.3f}", "-i", str(src), "-map", "0:v", "-map", "1:a:0?",
         "-t", f"{(f1 - f0) / fps:.3f}",
         "-c:v", "libx264", "-crf", str(RUN.crf), "-preset", RUN.preset,
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", RUN.audio_bitrate,
         str(tmp)], stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(str(src))
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    i = 0
    try:
        while i < f1:
            ok, frame = cap.read()
            if not ok:
                break
            if i >= f0:
                k = i - f0
                s = int(round(sides[k])); x = int(round(xs[k])); y = int(round(ys[k]))
                pad_l, pad_t = max(0, -x), max(0, -y)
                pad_r, pad_b = max(0, x + s - W), max(0, y + s - H)
                piece = frame[max(0, y):min(H, y + s), max(0, x):min(W, x + s)]
                if pad_l or pad_t or pad_r or pad_b:
                    piece = cv2.copyMakeBorder(piece, pad_t, pad_b, pad_l, pad_r,
                                               cv2.BORDER_CONSTANT, value=(0, 0, 0))
                enc.stdin.write(cv2.resize(piece, (RENDER_RES, RENDER_RES),
                                           interpolation=cv2.INTER_AREA).tobytes())
            i += 1
    except OSError:
        cap.release(); enc.stdin.close(); enc.wait()
        tmp.unlink(missing_ok=True)
        return False
    cap.release()
    enc.stdin.close()
    if enc.wait() != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _measure(track, found, crop, f0, f1, fps, W, H, rendered: Path, stem, src_name):
    sl = slice(f0, f1)
    fh = track["h"][sl]
    xs, ys, sides = crop["x"], crop["y"], crop["side"]
    fnd = found[sl]
    scale_out = RENDER_RES / np.maximum(sides, 1.0)
    face_out = (fh * scale_out)[fnd]
    centers = np.stack([xs + sides / 2, ys + sides / 2], axis=1)
    vel = np.linalg.norm(np.diff(centers, axis=0), axis=1) / np.maximum(sides[1:], 1)
    ok = crop["ok_frames"]
    blur, bright = _sample_output_quality(rendered, REC.blur_resample)
    n = f1 - f0
    return {
        "stem": stem, "source": src_name, "status": "rendered",
        "frames": int(n), "fps": float(fps), "src_w": W, "src_h": H,
        "face_lost_frac": float(1.0 - fnd.mean()) if n else 1.0,
        "face_out_avg_1280": float(face_out.mean()) if len(face_out) else 0.0,
        "face_out_min_1280": float(face_out.min()) if len(face_out) else 0.0,
        "face_out_max_1280": float(face_out.max()) if len(face_out) else 0.0,
        "center_jitter": float(vel.std()) if len(vel) else 0.0,
        "completeness": float(ok[fnd].mean()) if fnd.any() else 0.0,
        "hair_margin": crop["hair_margin"], "shoulder_margin": crop["shoulder_margin"],
        "pad_frac": 0.0, "blur_var_1280": blur, "brightness": bright,
        "yaw_abs_mean": float(np.abs(track["yaw"][sl][fnd]).mean()) if fnd.any() else 0.0,
        "pitch_abs_mean": float(np.abs(track["pitch"][sl][fnd]).mean()) if fnd.any() else 0.0,
        "roll_abs_mean": float(np.abs(track["roll"][sl][fnd]).mean()) if fnd.any() else 0.0,
        "face_src_avg": float(fh[fnd].mean()) if fnd.any() else 0.0,
        "crop_side_avg": float(sides.mean()),
        "mid_frame": int(n // 2),
        "mid_box": [float(xs[n // 2]), float(ys[n // 2]), float(sides[n // 2])],
        "mid_face": [float(track["cx"][sl][n // 2]), float(track["cy"][sl][n // 2]),
                     float(track["w"][sl][n // 2]), float(track["h"][sl][n // 2])],
    }


def _confidence(row: dict) -> str:
    a = RUN.accept
    m = min(row["face_avg"] / a.min_avg_face, row["face_min"] / a.min_min_face,
            row["blur_var"] / a.min_blur_var,
            row["completeness"] / a.min_completeness)
    return "high" if m >= 1.15 else "medium" if m >= 1.05 else "low"


def _classify(orig_reason: str, rec: dict, inspection: dict) -> str:
    """Step 4: what was the rejection, really?"""
    if not rec.get("recovered"):
        return "correct rejection"
    method = rec.get("method", "")
    if method == "blur_remeasure":
        return "borderline rejection (measurement noise)"
    if method == "segmentation":
        return "wrong segmentation (mixed-quality clip)"
    if "face_lost" in orig_reason and inspection.get("detect_frac", 0) > 0.95:
        return "face detector failure (stride/resolution)"
    if "head_clipped" in orig_reason:
        return "wrong crop (smoothing lagged motion)"
    return "false rejection"


def recover_clip(task: dict) -> dict:
    row = pd.Series(task["row"])
    stem = row["clip"]                 # NEVER row.clip - pandas method
    state_f = V3_STATE / f"{stem}.json"
    if state_f.exists():
        return json.loads(state_f.read_text(encoding="utf-8"))
    src = SRC_ACCEPTED / row["source"]
    rec = {"clip": stem, "source": row["source"],
           "original_reason": row["reject_reason"], "recovered": False,
           "method": "", "confidence": "", "notes": "", "inspection": {}}

    def _finish(**kw):
        rec.update(kw)
        rec["classification"] = _classify(row["reject_reason"], rec,
                                          rec.get("inspection", {}))
        state_f.parent.mkdir(parents=True, exist_ok=True)
        state_f.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        return rec

    if not src.exists():
        return _finish(method="none", notes="source missing")

    # fresh candidate: full decode + visual inspection + filmstrip
    samples, n, W, H, fps, inspection = _detect_and_inspect(src, stem)
    rec["inspection"] = inspection
    if n == 0 or not samples:
        return _finish(method="redetect",
                       notes="unreadable or no face at recovery params")

    track, found = interpolate_track(samples, n, RUN.crop.max_gap_frames)
    crop_cfg = replace(RUN.crop, smooth_window_s=REC.smooth_window_s,
                       detect_stride=REC.detect_stride,
                       detect_max_dim=REC.detect_max_dim)
    crop = solve_crop(track, found, W, H, fps, crop_cfg)

    def _try(f0, f1, crop_obj, trk, fnd, method):
        dest = V3 / "render" / f"{stem}.mp4"
        if not _render_range(src, dest, crop_obj, f0, f1, fps):
            return None
        state = _measure(trk, fnd, crop_obj, f0, f1, fps, W, H, dest, stem,
                         row["source"])
        vrow = variant_row(state, RENDER_RES)
        rec["last_metrics"] = vrow
        rec["mid_box"] = state["mid_box"]
        rec["mid_frame_abs"] = int(f0 + state["mid_frame"])
        if vrow["accepted"]:
            acc = V3 / "accepted" / f"{stem}.mp4"
            acc.parent.mkdir(parents=True, exist_ok=True)
            if not acc.exists():
                shutil.copyfile(dest, acc)
            return _finish(recovered=True, method=method,
                           confidence=_confidence(vrow), new_metrics=vrow,
                           notes=f"passes all original thresholds "
                                 f"(face {vrow['face_avg']:.0f}px, "
                                 f"completeness {vrow['completeness']:.3f})")
        return None

    # cheap honest win first: blur-only rejects re-measured densely on the
    # existing v2 output (same standards, better measurement)
    if row["reject_reason"] == "blurry":
        v2_file = V2 / "rejected" / f"{stem}.mp4"
        if v2_file.exists():
            blur, _ = _sample_output_quality(v2_file, REC.blur_resample)
            if blur >= RUN.accept.min_blur_var:
                dest = V3 / "accepted" / f"{stem}.mp4"
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copyfile(v2_file, dest)
                new_row = dict(task["row"], blur_var=blur, accepted=True,
                               reject_reason="")
                return _finish(recovered=True, method="blur_remeasure",
                               confidence="medium", new_metrics=new_row,
                               notes=f"blur {row['blur_var']:.0f}->{blur:.0f} "
                                     f"with {REC.blur_resample} samples")

    out = _try(0, n, crop, track, found, "redetect_full")
    if out:
        return out

    good = found & crop["ok_frames"]
    seg = _best_segment(good, int(REC.min_segment_s * fps))
    if seg:
        f0, f1 = seg
        sub_track = {k: v[f0:f1] for k, v in track.items()}
        sub_found = found[f0:f1]
        sub_crop = solve_crop(sub_track, sub_found, W, H, fps, crop_cfg)
        out = _try(f0, f1, sub_crop, sub_track, sub_found, "segmentation")
        if out:
            out["segment"] = [int(f0), int(f1)]
            state_f.write_text(json.dumps(out, indent=1), encoding="utf-8")
            return out

    return _finish(method="redetect+segmentation",
                   notes="no configuration reached accepted-dataset quality")


def main() -> int:
    df = pd.read_csv(V2 / "dataset.csv")
    rej = df[~df.accepted].reset_index(drop=True)
    for d in (V3 / "accepted", V3 / "rejected", V3 / "reports", V3 / "comparison",
              V3 / "render", V3_STATE, V3_STRIPS):
        d.mkdir(parents=True, exist_ok=True)
    tasks = [{"row": r.to_dict()} for _, r in rej.iterrows()]
    print(f"recovery audit: {len(tasks)} rejected clips from {V2}")

    results = []
    with ProcessPoolExecutor(max_workers=RUN.workers) as pool:
        futs = [pool.submit(recover_clip, t) for t in tasks]
        for i, f in enumerate(as_completed(futs), 1):
            try:
                results.append(f.result())
            except Exception as e:
                print(f"[recover] ERROR: {e}", flush=True)
            if i % 10 == 0 or i == len(tasks):
                rec_n = sum(1 for r in results if r.get("recovered"))
                print(f"[recover] {i}/{len(tasks)} audited, {rec_n} recovered",
                      flush=True)

    recovered_stems = {r["clip"] for r in results if r.get("recovered")}
    import os
    for f in (V2 / "rejected").glob("*.mp4"):
        if f.stem not in recovered_stems:
            t = V3 / "rejected" / f.name
            if not t.exists():
                try:
                    os.link(f, t)
                except OSError:
                    shutil.copyfile(f, t)

    from .recover_reports import write_all
    write_all(results, rej)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
