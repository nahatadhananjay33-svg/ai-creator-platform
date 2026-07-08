"""Deterministic placeholder asset generators (Phase C6).

For demos and hermetic tests we need real local files without downloading or
generating anything with AI. These helpers write **deterministic** placeholder
assets: a labelled solid image (Pillow) and a labelled solid video (FFmpeg).
They are plain synthetic files — not stock, not AI — so the pipeline has
something concrete to place on the timeline.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def generate_image(path: Path | str, *, width: int = 1280, height: int = 720,
                   color: tuple = (40, 90, 160), label: str = "") -> Path:
    """Write a solid PNG with an optional centred label + a border."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (width, height), color)
    d = ImageDraw.Draw(img)
    m = max(4, min(width, height) // 40)
    d.rectangle([m, m, width - m, height - m], outline=(255, 255, 255), width=m // 2 or 2)
    if label:
        # font-independent marker so output is byte-stable across environments.
        cx, cy, r = width // 2, height // 2, min(width, height) // 8
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=max(2, r // 6))
    img.save(path)
    return path


def generate_video(ffmpeg: str, path: Path | str, *, width: int = 1280, height: int = 720,
                   fps: int = 30, duration_s: float = 4.0,
                   color_hex: str = "0x1E5AA0") -> Path:
    """Write a short solid-colour MP4 (deterministic) via FFmpeg lavfi.

    Requires ``ffmpeg`` on PATH; used only by the demo's ffmpeg path (the mock
    backend and hermetic tests never decode video)."""
    import subprocess

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i",
         f"color=c={color_hex}:s={width}x{height}:r={fps}:d={duration_s}",
         "-vf", f"drawgrid=w={width // 8}:h={height // 8}:t=2:c=white@0.4",
         "-t", f"{duration_s}", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, capture_output=True, text=True)
    return path
