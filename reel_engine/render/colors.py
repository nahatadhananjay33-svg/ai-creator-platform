"""Colour helpers shared by the renderers (Phase C2).

The IR stores colours as RGB triples. Renderers need them in different forms:
the mock renderer writes BGR24 frame bytes; the FFmpeg renderer needs
``0xRRGGBB`` for the ``lavfi`` colour source.
"""
from __future__ import annotations


def clamp8(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else int(v)


def rgb_tuple(color) -> tuple:
    r, g, b = (clamp8(c) for c in color)
    return (r, g, b)


def rgb_to_hex(color) -> str:
    """``(0, 0, 255) -> '0x0000FF'`` (FFmpeg ``color=`` syntax)."""
    r, g, b = rgb_tuple(color)
    return f"0x{r:02X}{g:02X}{b:02X}"


def rgb_to_bgr_bytes(color) -> bytes:
    """One pixel as BGR24 bytes (the raw-AVI channel order)."""
    r, g, b = rgb_tuple(color)
    return bytes((b, g, r))


def hex_to_rgb(text: str) -> tuple:
    """Parse ``#RRGGBB`` or ``0xRRGGBB`` into an RGB triple."""
    t = text.lstrip("#")
    if t.lower().startswith("0x"):
        t = t[2:]
    if len(t) != 6:
        raise ValueError(f"not a #RRGGBB colour: {text!r}")
    return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
