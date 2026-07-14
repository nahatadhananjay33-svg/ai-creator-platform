"""Technical metadata via ffprobe, with an OpenCV fallback (offline, no models)."""
from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from .models import Orientation, VideoMeta


def _orientation(w: int, h: int) -> str:
    if not w or not h:
        return Orientation.LANDSCAPE.value
    r = w / h
    if abs(r - 1.0) < 0.05:
        return Orientation.SQUARE.value
    return Orientation.PORTRAIT.value if r < 1 else Orientation.LANDSCAPE.value


def _ffprobe(path: Path):
    if not shutil.which("ffprobe"):
        return None
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_format", "-show_streams", str(path)],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout else None
    except Exception:
        return None


def _fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        v = stream.get(key)
        if v and v not in ("0/0", "0"):
            try:
                return float(Fraction(v))
            except Exception:
                pass
    return 0.0


def probe(path) -> VideoMeta:
    path = Path(path)
    size_mb = round(path.stat().st_size / 1e6, 2)
    data = _ffprobe(path)

    if data:
        vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        fmt = data.get("format", {})
        w, h = int(vs.get("width") or 0), int(vs.get("height") or 0)
        fps = _fps(vs)
        dur = float(fmt.get("duration") or vs.get("duration") or 0.0)
        nb = int(vs.get("nb_frames") or 0) or int(round(dur * fps))
        codec = vs.get("codec_name") or ""
        bitrate = int(fmt.get("bit_rate") or vs.get("bit_rate") or 0)
        ctime = (fmt.get("tags", {}) or {}).get("creation_time", "")
    else:                                          # OpenCV fallback
        w = h = nb = 0
        fps = dur = 0.0
        codec, bitrate, ctime = "", 0, ""
        try:
            import cv2
            cap = cv2.VideoCapture(str(path))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
            nb = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00 ") or "raw"
            cap.release()
            dur = nb / fps if fps else 0.0
            bitrate = int(size_mb * 1e6 * 8 / dur) if dur else 0
        except Exception:
            pass

    ar = round(w / h, 3) if h else 0.0
    return VideoMeta(filename=path.name, duration=round(dur, 2), width=w, height=h,
                     fps=round(fps, 2), aspect_ratio=ar, orientation=_orientation(w, h),
                     file_size_mb=size_mb, codec=codec, bitrate=bitrate,
                     frame_count=nb, creation_time=ctime)
