"""Face detection + rough head pose on sampled frames (MediaPipe, CPU)."""
from __future__ import annotations

import math

import cv2
import numpy as np

_detector = None

# canonical 3D reference points for the 6 MediaPipe FaceDetection keypoints
# (right eye, left eye, nose tip, mouth center, right tragion, left tragion)
_MODEL_3D = np.array([
    [-30.0, -30.0, -30.0],
    [30.0, -30.0, -30.0],
    [0.0, 0.0, 0.0],
    [0.0, 30.0, -20.0],
    [-60.0, -20.0, -70.0],
    [60.0, -20.0, -70.0],
], dtype=np.float64)


def _get_detector():
    global _detector
    if _detector is None:
        import mediapipe as mp
        _detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.4)
    return _detector


def detect_frame(frame_bgr: np.ndarray, max_dim: int):
    """Detect the most confident face.

    Returns None or dict(cx, cy, w, h, score, yaw, pitch, roll) in source pixels.
    """
    H, W = frame_bgr.shape[:2]
    scale = min(1.0, max_dim / max(H, W))
    small = cv2.resize(frame_bgr, (int(W * scale), int(H * scale)),
                       interpolation=cv2.INTER_AREA) if scale < 1.0 else frame_bgr
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    res = _get_detector().process(rgb)
    if not res.detections:
        return None
    det = max(res.detections, key=lambda d: d.score[0])
    box = det.location_data.relative_bounding_box
    kps = det.location_data.relative_keypoints
    cx = (box.xmin + box.width / 2) * W
    cy = (box.ymin + box.height / 2) * H
    w = box.width * W
    h = box.height * H

    yaw = pitch = roll = 0.0
    try:
        pts2d = np.array([[k.x * W, k.y * H] for k in kps[:6]], dtype=np.float64)
        f = float(W)
        cam = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]], dtype=np.float64)
        ok, rvec, _ = cv2.solvePnP(_MODEL_3D, pts2d, cam, None,
                                   flags=cv2.SOLVEPNP_EPNP)
        if ok:
            R, _ = cv2.Rodrigues(rvec)
            sy = math.hypot(R[0, 0], R[1, 0])
            pitch = math.degrees(math.atan2(-R[2, 0], sy))
            yaw = math.degrees(math.atan2(R[1, 0], R[0, 0]))
            roll = math.degrees(math.atan2(R[2, 1], R[2, 2]))
    except Exception:
        pass

    return {"cx": cx, "cy": cy, "w": w, "h": h, "score": float(det.score[0]),
            "yaw": yaw, "pitch": pitch, "roll": roll}
