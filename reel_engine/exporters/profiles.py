"""Per-platform export profiles (Phase C2).

An export profile is pure data: a target resolution/aspect the master reel is
fitted into. The *math* here (target dims + letterbox fit) is shared by both
renderers — the FFmpeg renderer turns it into a ``scale``+``pad`` filter, the
mock renderer scales pixels directly — so this module is unit-tested on its own,
with no FFmpeg.

C2 ships the three required aspects; adding TikTok/Facebook/LinkedIn later is a
one-line registry entry (they reuse these same three shapes).
"""
from __future__ import annotations

from dataclasses import dataclass

from reel_engine.interfaces.types import aspect_ratio_string


@dataclass(frozen=True)
class ExportProfile:
    """A target the master is fitted into for one platform/aspect."""

    name: str
    width: int
    height: int
    fit: str = "pad"          # "pad" (letterbox) | "crop" (C2 uses pad)
    description: str = ""

    @property
    def aspect(self) -> str:
        return aspect_ratio_string(self.width, self.height)


#: The three required aspects. Platform names (IG/TikTok/YT/FB/LinkedIn) map onto
#: these shapes; the registry stays intentionally tiny for the walking skeleton.
_PROFILES: dict[str, ExportProfile] = {
    p.name: p for p in (
        ExportProfile("reel_9x16", 1080, 1920, description="IG Reels / YT Shorts / TikTok"),
        ExportProfile("square_1x1", 1080, 1080, description="Square feed (IG/FB/LinkedIn)"),
        ExportProfile("landscape_16x9", 1920, 1080, description="YouTube / landscape"),
    )
}


def get_profile(name: str) -> ExportProfile:
    try:
        return _PROFILES[name]
    except KeyError:
        raise KeyError(f"Unknown export profile {name!r}; known: {sorted(_PROFILES)}") from None


def profile_names() -> list[str]:
    return sorted(_PROFILES)


def all_profiles() -> list[ExportProfile]:
    return [_PROFILES[n] for n in profile_names()]


def _even(n: int) -> int:
    """Round down to an even integer (yuv420p encoders require even dims)."""
    n = int(round(n))
    return n - (n % 2)


@dataclass(frozen=True)
class FitBox:
    """Result of fitting a source into a target: the scaled inner size and the
    padding offsets that centre it (letterbox)."""

    scaled_w: int
    scaled_h: int
    pad_x: int
    pad_y: int
    target_w: int
    target_h: int


def fit_box(src_w: int, src_h: int, dst_w: int, dst_h: int, mode: str = "pad") -> FitBox:
    """Compute the centred scale+pad (or scale+crop) box mapping a source frame
    into a target profile, preserving aspect ratio. All returned dims are even."""
    if src_w <= 0 or src_h <= 0 or dst_w <= 0 or dst_h <= 0:
        raise ValueError("fit_box requires positive dimensions")
    choose = min if mode == "pad" else max
    scale = choose(dst_w / src_w, dst_h / src_h)
    scaled_w = max(2, _even(src_w * scale))
    scaled_h = max(2, _even(src_h * scale))
    pad_x = _even((dst_w - scaled_w) / 2)
    pad_y = _even((dst_h - scaled_h) / 2)
    return FitBox(scaled_w, scaled_h, pad_x, pad_y, dst_w, dst_h)
