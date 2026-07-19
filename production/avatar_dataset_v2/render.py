"""Per-clip pipeline: decode -> detect -> solve crop -> render master 1280.

Runs inside a worker process. Writes the master render plus a JSON state file
with the full track + intrinsic metrics; variant encodes happen in stage 2.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .config import RENDER_RES, RUN, STATE_DIR, RENDER_DIR, safe_stem
from .detect import detect_frame
from .tracking import interpolate_track, solve_crop


def _ffprobe_fps(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    try:
        # csv output for MOV files carries a trailing comma: "60/1,"
        raw = out.stdout.strip().splitlines()[0].strip().rstrip(",")
        num, den = raw.split("/")
        return float(num) / float(den)
    except Exception:
        return 30.0


def process_clip(src: Path) -> dict:
    stem = safe_stem(src.name)
    state_path = STATE_DIR / f"{stem}.json"
    master = RENDER_DIR / f"{stem}.mp4"
    if state_path.exists() and master.exists() and master.stat().st_size > 0:
        return json.loads(state_path.read_text(encoding="utf-8"))

    cap = cv2.VideoCapture(str(src))
    if not cap.isOpened():
        return _fail(state_path, stem, src, "unreadable")
    fps = _ffprobe_fps(src)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # ---- pass 1: sampled detection
    samples: dict[int, dict] = {}
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if n % RUN.crop.detect_stride == 0:
            det = detect_frame(frame, RUN.crop.detect_max_dim)
            if det is not None:
                samples[n] = det
        n += 1
    cap.release()
    if n == 0:
        return _fail(state_path, stem, src, "empty")

    track, found = interpolate_track(samples, n, RUN.crop.max_gap_frames)
    face_lost_frac = 1.0 - (float(found.mean()) if n else 0.0)
    if not found.any():
        return _fail(state_path, stem, src, "no_face")

    crop = solve_crop(track, found, W, H, fps, RUN.crop)

    # ---- pass 2: crop + render master
    cap = cv2.VideoCapture(str(src))
    tmp = master.with_suffix(".tmp.mp4")
    enc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{RENDER_RES}x{RENDER_RES}", "-r", f"{fps:.6f}", "-i", "-",
         "-i", str(src), "-map", "0:v", "-map", "1:a:0?",
         "-c:v", "libx264", "-crf", str(RUN.crf), "-preset", RUN.preset,
         # no -shortest: with a mis-declared fps it kills the mux mid-pipe;
         # the video stream is exactly n frames long anyway
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", RUN.audio_bitrate,
         str(tmp)],
        stdin=subprocess.PIPE)
    xs, ys, sides = crop["x"], crop["y"], crop["side"]
    i = 0
    try:
        _stream_frames(cap, enc, xs, ys, sides, n, W, H)
    except OSError:
        cap.release()
        enc.stdin.close()
        enc.wait()
        tmp.unlink(missing_ok=True)
        return _fail(state_path, stem, src, "encode_pipe_broken")
    cap.release()
    enc.stdin.close()
    if enc.wait() != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return _fail(state_path, stem, src, "encode_failed")
    tmp.replace(master)

    # ---- intrinsic metrics (variant-independent)
    fh = track["h"]
    scale_out = RENDER_RES / np.maximum(sides, 1.0)
    face_out = (fh * scale_out)[found]
    centers = np.stack([xs + sides / 2, ys + sides / 2], axis=1)
    vel = np.linalg.norm(np.diff(centers, axis=0), axis=1) / np.maximum(sides[1:], 1)
    pad_frac = float(np.mean((xs < 0) | (ys < 0) |
                             (xs + sides > W) | (ys + sides > H)))

    blur, bright = _sample_output_quality(master)
    state = {
        "stem": stem, "source": src.name, "status": "rendered",
        "frames": int(n), "fps": float(fps), "src_w": W, "src_h": H,
        "face_lost_frac": float(face_lost_frac),
        "face_out_avg_1280": float(face_out.mean()),
        "face_out_min_1280": float(face_out.min()),
        "face_out_max_1280": float(face_out.max()),
        "center_jitter": float(vel.std()) if len(vel) else 0.0,
        "completeness": crop["completeness"],
        "hair_margin": crop["hair_margin"],
        "shoulder_margin": crop["shoulder_margin"],
        "pad_frac": pad_frac,
        "blur_var_1280": blur, "brightness": bright,
        "yaw_abs_mean": float(np.abs(track["yaw"][found]).mean()),
        "pitch_abs_mean": float(np.abs(track["pitch"][found]).mean()),
        "roll_abs_mean": float(np.abs(track["roll"][found]).mean()),
        "face_src_avg": float(fh[found].mean()),
        "crop_side_avg": float(sides.mean()),
        # mid-frame crop box for the comparison sheets
        "mid_frame": int(n // 2),
        "mid_box": [float(xs[n // 2]), float(ys[n // 2]), float(sides[n // 2])],
        "mid_face": [float(track["cx"][n // 2]), float(track["cy"][n // 2]),
                     float(track["w"][n // 2]), float(track["h"][n // 2])],
    }
    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state


def _stream_frames(cap, enc, xs, ys, sides, n, W, H):
    import cv2
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok or i >= n:
            break
        s = int(round(sides[i]))
        x = int(round(xs[i]))
        y = int(round(ys[i]))
        pad_l = max(0, -x)
        pad_t = max(0, -y)
        pad_r = max(0, x + s - W)
        pad_b = max(0, y + s - H)
        piece = frame[max(0, y):min(H, y + s), max(0, x):min(W, x + s)]
        if pad_l or pad_t or pad_r or pad_b:
            piece = cv2.copyMakeBorder(piece, pad_t, pad_b, pad_l, pad_r,
                                       cv2.BORDER_CONSTANT, value=(0, 0, 0))
        piece = cv2.resize(piece, (RENDER_RES, RENDER_RES),
                           interpolation=cv2.INTER_AREA)
        enc.stdin.write(piece.tobytes())
        i += 1


def _sample_output_quality(video: Path, k: int = 8):
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    blurs, brights = [], []
    for f in np.linspace(0, max(0, n - 1), k).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f))
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurs.append(cv2.Laplacian(gray, cv2.CV_64F).var())
        brights.append(gray.mean())
    cap.release()
    return (float(np.mean(blurs)) if blurs else 0.0,
            float(np.mean(brights)) if brights else 0.0)


def _fail(state_path: Path, stem: str, src: Path, reason: str) -> dict:
    state = {"stem": stem, "source": src.name, "status": "failed",
             "reject_reason": reason}
    state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return state
