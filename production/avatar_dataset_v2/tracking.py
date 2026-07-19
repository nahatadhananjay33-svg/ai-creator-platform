"""Turn a sparse face track into a smooth, jitter-free square crop track.

Guarantees per frame (up to `completeness` reporting):
  * full head + hair headroom above the face box
  * neck + shoulders below
  * ears + lateral margin on both sides
The crop is a square, moving-average smoothed, then iteratively expanded so
the smoothed track still contains every frame's required region — smoothing
must never become the reason a chin or hairline gets clipped.
"""
from __future__ import annotations

import numpy as np

from .config import CropCfg


def interpolate_track(samples: dict[int, dict], n_frames: int, max_gap: int):
    """Linear-interpolate sampled detections onto every frame index.

    Returns (track arrays dict, face_found bool-array). Frames beyond
    `max_gap` of any detection are marked not-found (track holds nearest value).
    """
    idx = np.array(sorted(samples), dtype=np.int64)
    found = np.zeros(n_frames, dtype=bool)
    out = {k: np.zeros(n_frames, dtype=np.float64)
           for k in ("cx", "cy", "w", "h", "yaw", "pitch", "roll")}
    if len(idx) == 0:
        return out, found
    frames = np.arange(n_frames)
    for k in out:
        vals = np.array([samples[i][k] for i in idx], dtype=np.float64)
        out[k] = np.interp(frames, idx, vals)
    # distance to the nearest real detection decides "found"
    pos = np.searchsorted(idx, frames)
    left = idx[np.clip(pos - 1, 0, len(idx) - 1)]
    right = idx[np.clip(pos, 0, len(idx) - 1)]
    dist = np.minimum(np.abs(frames - left), np.abs(frames - right))
    found = dist <= max_gap
    return out, found


def _required_region(track, cfg: CropCfg):
    """Per-frame region that must be inside the crop (x0, y0, x1, y1)."""
    cx, cy, w, h = track["cx"], track["cy"], track["w"], track["h"]
    x0 = cx - cfg.side_width * w / 2
    x1 = cx + cfg.side_width * w / 2
    y0 = cy - cfg.top_hair * h
    y1 = cy + cfg.bottom_shoulders * h
    return x0, y0, x1, y1


def _smooth(a: np.ndarray, win: int) -> np.ndarray:
    if win <= 1 or len(a) < 3:
        return a.copy()
    win = min(win | 1, len(a) - (1 - len(a) % 2))   # odd, <= len
    pad = win // 2
    padded = np.pad(a, pad, mode="edge")
    kernel = np.ones(win) / win
    return np.convolve(padded, kernel, mode="valid")


def solve_crop(track, found: np.ndarray, frame_w: int, frame_h: int,
               fps: float, cfg: CropCfg):
    """Returns per-frame square crop (x, y, side) float arrays + completeness."""
    dx0, dy0, dx1, dy1 = _required_region(track, cfg)   # desired (may exit frame)
    # the crop only has to contain what the source actually shows; the rest
    # is reported as hair/shoulder visibility instead of forcing black padding
    x0 = np.clip(dx0, 0, frame_w)
    x1 = np.clip(dx1, 0, frame_w)
    y0 = np.clip(dy0, 0, frame_h)
    y1 = np.clip(dy1, 0, frame_h)
    hair_vis = float(np.mean(((track["cy"] - y0) /
                              np.maximum(track["cy"] - dy0, 1e-6))[found])) \
        if found.any() else 0.0
    shoulder_vis = float(np.mean(((y1 - track["cy"]) /
                                  np.maximum(dy1 - track["cy"], 1e-6))[found])) \
        if found.any() else 0.0
    side_req = np.maximum(x1 - x0, y1 - y0)
    ccx = (x0 + x1) / 2
    ccy = y0 + side_req / 2          # anchor: hair headroom defines the top

    win = max(3, int(round(cfg.smooth_window_s * fps)))
    scx, scy = _smooth(ccx, win), _smooth(ccy, win)
    sside = _smooth(side_req, win)

    # expansion passes: the smoothed crop must still contain the raw region.
    # Each pass shifts the center toward uncovered sides and grows the side,
    # then re-smooths (which can re-introduce small violations, hence loop).
    for _ in range(6):
        need_l = np.maximum(0.0, (scx - sside / 2) - x0)   # uncovered on the left
        need_r = np.maximum(0.0, x1 - (scx + sside / 2))
        need_t = np.maximum(0.0, (scy - sside / 2) - y0)
        need_b = np.maximum(0.0, y1 - (scy + sside / 2))
        worst = float(np.maximum.reduce([need_l, need_r, need_t, need_b]).max(initial=0.0))
        if worst < 1.0:
            break
        scx = _smooth(scx + (need_r - need_l) / 2, win)
        scy = _smooth(scy + (need_b - need_t) / 2, win)
        sside = _smooth(sside + np.maximum(need_l + need_r, need_t + need_b), win)

    sside = sside * 1.03             # safety inflation: edges must not be exact
    # keep the crop inside reasonable bounds (padding handles the rest)
    sside = np.clip(sside, 32.0, 4.0 * max(frame_w, frame_h))
    x = scx - sside / 2
    y = scy - sside / 2

    # slide the box back inside the frame wherever it fits: a shift can never
    # uncover the (frame-clipped) required region, and it eliminates padding
    # for sources that actually contain the full head+shoulders region
    def _clamp(pos, lo_req, hi_req, frame_dim):
        fits = sside <= frame_dim
        lo = np.maximum(hi_req - sside, 0.0)
        hi = np.minimum(lo_req, frame_dim - sside)
        clamped = np.clip(pos, np.minimum(lo, hi), np.maximum(lo, hi))
        centered = (lo_req + hi_req) / 2 - sside / 2
        return np.where(fits, clamped, centered)

    x = _clamp(x, x0, x1, float(frame_w))
    y = _clamp(y, y0, y1, float(frame_h))

    cx0, cy0, cx1, cy1 = x, y, x + sside, y + sside
    ok = (cx0 <= x0 + 1) & (cy0 <= y0 + 1) & (cx1 >= x1 - 1) & (cy1 >= y1 - 1)
    completeness = float(np.mean(ok[found])) if found.any() else 0.0

    return {
        "x": x, "y": y, "side": sside,
        "completeness": completeness,
        "hair_margin": hair_vis,
        "shoulder_margin": shoulder_vis,
        "ok_frames": ok,          # per-frame coverage validity (for segmentation)
    }
