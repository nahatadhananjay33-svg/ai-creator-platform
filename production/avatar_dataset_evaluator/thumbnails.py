"""Save a small thumbnail (mid-frame) per video."""
from __future__ import annotations

from pathlib import Path

from .models import VideoMeta


def make_thumbnail(video_path, out_dir: Path, meta: VideoMeta, size: int = 320) -> str:
    import cv2
    out = Path(out_dir) / (Path(video_path).stem + ".jpg")
    if out.exists():
        return str(out)
    cap = cv2.VideoCapture(str(video_path))
    n = meta.frame_count or int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if n > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, n // 2)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return ""
    h, w = frame.shape[:2]
    scale = size / max(h, w) if max(h, w) else 1.0
    thumb = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return str(out)
