"""Classical-CV visual analysis over sampled frames.

Face detection uses OpenCV's bundled Haar cascades (Viola-Jones — classical, no
deep learning, no download, CPU). Everything else is DSP/statistics: brightness,
Laplacian-variance sharpness, phase-correlation camera motion, histogram scene
cuts, and lower-face motion as a speaking proxy. All values are estimates.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from .config import Config
from .models import FaceView, VideoMeta, VisualAnalysis

_cascades: dict = {}


def _cascade(name: str):
    import cv2
    if name not in _cascades:
        _cascades[name] = cv2.CascadeClassifier(cv2.data.haarcascades + name)
    return _cascades[name]


def _time_of_day(creation_time: str) -> str:
    m = re.search(r"T(\d\d):", creation_time or "")
    if not m:
        return "unknown"
    hh = int(m.group(1))
    if 5 <= hh < 12:
        return "morning"
    if 12 <= hh < 17:
        return "afternoon"
    if 17 <= hh < 21:
        return "evening"
    return "night"


def _setting(lighting_mean: float) -> str:
    # Low-confidence heuristic: brighter scenes skew outdoor. Flagged as such in docs.
    if lighting_mean >= 150:
        return "outdoor?"
    if lighting_mean <= 90:
        return "indoor?"
    return "unknown"


def _empty(meta: VideoMeta) -> VisualAnalysis:
    return VisualAnalysis(
        face_visibility_pct=0.0, avg_face_size_pct=0.0, frontal_pct=0.0, profile_pct=0.0,
        face_view=FaceView.NONE.value, head_rotation="unknown", lighting_mean=0.0,
        lighting_consistency=0.0, camera_stability=0.0, motion_blur=0.0, occlusion_pct=0.0,
        eye_visibility_pct=0.0, mouth_visibility_pct=0.0, speaking_pct=0.0, walking_pct=0.0,
        stationary_pct=0.0, camera_movement=0.0, scene_changes=0,
        time_of_day=_time_of_day(meta.creation_time), setting="unknown", expression="neutral")


def analyze(path, meta: VideoMeta, cfg: Config) -> VisualAnalysis:
    import cv2

    cap = cv2.VideoCapture(str(path))
    n = meta.frame_count or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = meta.width or int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = meta.height or int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if n <= 1 or w == 0 or h == 0:
        cap.release()
        return _empty(meta)

    k = min(cfg.frame_samples, max(2, n - 1))
    idxs = np.linspace(0, max(0, n - 2), k).astype(int)
    minsize = max(20, int(cfg.detect_min_size_frac * h))
    frame_area = float(w * h)
    diag = (w * w + h * h) ** 0.5

    front = _cascade("haarcascade_frontalface_default.xml")
    prof = _cascade("haarcascade_profileface.xml")
    eye = _cascade("haarcascade_eye.xml")
    smile = _cascade("haarcascade_smile.xml")

    face_frames = frontal = left = right = 0
    eyes_ok = mouth_ok = occluded = smiles = 0
    face_sizes, lumas, blurs = [], [], []
    shifts, global_motion, mouth_motion = [], [], []
    hist_prev, scene_changes = None, 0

    for i in idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f1 = cap.read()
        if not ok:
            continue
        ok2, f2 = cap.read()
        g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
        lumas.append(float(g1.mean()))
        blurs.append(float(cv2.Laplacian(g1, cv2.CV_64F).var()))

        hist = cv2.calcHist([g1], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)
        if hist_prev is not None:
            corr = cv2.compareHist(hist_prev, hist, cv2.HISTCMP_CORREL)
            if corr < (1 - cfg.scene_change_hist_delta):
                scene_changes += 1
        hist_prev = hist

        ff = front.detectMultiScale(g1, cfg.detect_scale, cfg.detect_neighbors, minSize=(minsize, minsize))
        best, view = None, None
        if len(ff):
            best, view = max(ff, key=lambda b: b[2] * b[3]), "frontal"
        else:
            pf = prof.detectMultiScale(g1, cfg.detect_scale, cfg.detect_neighbors, minSize=(minsize, minsize))
            if len(pf):
                best, view = max(pf, key=lambda b: b[2] * b[3]), "left"
            else:
                pr = prof.detectMultiScale(cv2.flip(g1, 1), cfg.detect_scale,
                                           cfg.detect_neighbors, minSize=(minsize, minsize))
                if len(pr):
                    best, view = max(pr, key=lambda b: b[2] * b[3]), "right"

        if best is not None:
            face_frames += 1
            x, y, fw, fh = best
            face_sizes.append(fw * fh / frame_area * 100)
            frontal += view == "frontal"
            left += view == "left"
            right += view == "right"
            roi = g1[y:y + fh, x:x + fw]
            if roi.size:
                e = eye.detectMultiScale(roi, 1.1, 4)
                lower = roi[fh // 2:, :]
                s = smile.detectMultiScale(lower, 1.7, 15) if lower.size else ()
                eyes_ok += len(e) > 0
                if len(s):
                    mouth_ok += 1
                    smiles += 1
                if not len(e) and not len(s):
                    occluded += 1
                if ok2 and view == "frontal" and f2.shape == f1.shape and lower.size:
                    g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
                    l2 = g2[y + fh // 2:y + fh, x:x + fw]
                    if l2.shape == lower.shape:
                        mouth_motion.append(float(np.abs(lower.astype(np.int16) - l2.astype(np.int16)).mean()))

        if ok2 and f2.shape == f1.shape:
            g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(g1), np.float32(g2))
            shifts.append((dx * dx + dy * dy) ** 0.5)
            global_motion.append(float(np.abs(g1.astype(np.int16) - g2.astype(np.int16)).mean()))

    cap.release()

    ns = max(1, len(idxs))
    fc = max(1, face_frames)
    face_vis = face_frames / ns * 100
    avg_face = float(np.median(face_sizes)) if face_sizes else 0.0
    frontal_pct = frontal / fc * 100
    profile_pct = (left + right) / fc * 100

    if face_frames == 0:
        view = FaceView.NONE.value
    elif frontal >= left + right:
        view = FaceView.FRONTAL.value
    else:
        view = FaceView.LEFT_PROFILE.value if left >= right else FaceView.RIGHT_PROFILE.value
    head_rot = ("extreme" if profile_pct >= cfg.extreme_rotation_profile_pct
                else "moderate" if profile_pct >= 30 else "near_frontal")

    lighting_mean = float(np.mean(lumas)) if lumas else 0.0
    lighting_consistency = float(max(0.0, 1 - np.std(lumas) / 60.0)) if lumas else 0.0
    motion_blur = float(np.median(blurs)) if blurs else 0.0

    norm_shifts = [s / diag for s in shifts] if shifts else [0.0]
    camera_movement = float(min(1.0, np.mean(norm_shifts) * 20))
    camera_stability = float(max(0.0, 1 - np.std(norm_shifts) * 40)) if len(norm_shifts) > 1 else 1.0
    gm = float(np.mean(global_motion)) if global_motion else 0.0
    walking = camera_movement > 0.15 and gm > 8
    speaking_pct = float(min(100.0, np.mean(mouth_motion) / cfg.speaking_mouth_motion * 100)) if mouth_motion else 0.0
    expression = ("smiling" if smiles / fc > 0.3 else "talking" if speaking_pct > 30 else "neutral")

    return VisualAnalysis(
        face_visibility_pct=round(face_vis, 1), avg_face_size_pct=round(avg_face, 2),
        frontal_pct=round(frontal_pct, 1), profile_pct=round(profile_pct, 1), face_view=view,
        head_rotation=head_rot, lighting_mean=round(lighting_mean, 1),
        lighting_consistency=round(lighting_consistency, 2), camera_stability=round(camera_stability, 2),
        motion_blur=round(motion_blur, 1), occlusion_pct=round(occluded / fc * 100, 1),
        eye_visibility_pct=round(eyes_ok / fc * 100, 1), mouth_visibility_pct=round(mouth_ok / fc * 100, 1),
        speaking_pct=round(speaking_pct, 1), walking_pct=100.0 if walking else 0.0,
        stationary_pct=0.0 if walking else 100.0, camera_movement=round(camera_movement, 2),
        scene_changes=scene_changes, time_of_day=_time_of_day(meta.creation_time),
        setting=_setting(lighting_mean), expression=expression)
