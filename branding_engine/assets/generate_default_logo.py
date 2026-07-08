"""Generate the packaged placeholder logo (Phase C5).

Deterministic, one-off asset generation with Pillow: a transparent-background
rounded badge with "AICP" initials, used by the branding demo and as the config
default when a creator has not supplied their own logo. Re-run to regenerate:

    python -m branding_engine.assets.generate_default_logo
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "default_logo.png"
SIZE = 512
_BG = (24, 119, 242, 255)      # brand blue badge
_FG = (255, 255, 255, 255)


def generate(out: Path = OUT) -> Path:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = SIZE // 12
    d.rounded_rectangle([m, m, SIZE - m, SIZE - m], radius=SIZE // 6, fill=_BG)
    # A simple, font-independent glyph: a bold ring + centre dot (a "record" mark).
    cx = cy = SIZE // 2
    r = SIZE // 4
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=_FG, width=SIZE // 20)
    d.ellipse([cx - r // 3, cy - r // 3, cx + r // 3, cy + r // 3], fill=_FG)
    img.save(out)
    return out


if __name__ == "__main__":
    print(generate())
