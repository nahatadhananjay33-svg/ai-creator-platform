"""Frozen value types for the Reels Engine (Phase C2 walking skeleton).

These are the **frozen contracts** other engines/products depend on — never on
internals (ARCHITECTURE.md rule #2). The model is a small, layered, declarative
IR — the "edit decision list" — separate from any renderer. Rendering is a pure
function of a :class:`Timeline` plus its assets, which is what gives caching,
resumability, and reproducibility for free in later phases.

Design for forward-compatibility: fields that later phases need (transitions,
per-clip transforms/keyframes, asset hashes) already exist as inert, defaulted
fields so C3+ can populate them without breaking the schema. C2 only *renders*
solid backgrounds, text overlays, and silent audio — everything else is carried
but unused.

Everything here is an immutable ``@dataclass(frozen=True)``; collections are
tuples (not lists) so a constructed object cannot be mutated in place. Nested
``dict`` fields (styles/metadata) are treated as read-only; serialization sorts
their keys so content hashing stays deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Bumped whenever the serialized Timeline schema changes incompatibly. serde
#: writes it into every project file; the loader validates/migrates against it.
#: v2 (Phase C4) added ``Timeline.caption_tracks``; v3 (Phase C5) added
#: ``Timeline.branding`` — both purely additive: v1/v2 projects still load (they
#: simply have no caption tracks / no branding).
TIMELINE_SCHEMA_VERSION = 3

#: RGB colour, 0-255 per channel (the IR is colour-space agnostic; renderers
#: convert to whatever their pipeline needs — e.g. BGR24 frames).
RGB = tuple


@dataclass(frozen=True)
class AssetRef:
    """A reference to one source asset.

    C2 assets are all *generated placeholders* (a solid colour, a text string,
    silent audio), so ``uri`` is a scheme-tagged string rather than a file path.
    ``content_hash`` is reserved for C3+ when real, downloaded assets are
    content-addressed in the asset store.
    """

    kind: str                       # "color" | "text" | "silent_audio" | "file"
    uri: str                        # "#0000FF" | the text | "generated:silent" | a path
    content_hash: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Transition:
    """How a scene enters/leaves. C2 supports only ``cut`` (a hard boundary,
    zero duration); the field exists so C4 can add fades/slides without a schema
    change."""

    kind: str = "cut"               # C2: "cut" only
    duration_s: float = 0.0


@dataclass(frozen=True)
class Clip:
    """One element placed on a track over a time range (relative to its scene).

    C2 clip kinds:
      - ``solid_color`` — a full-frame background fill (``color``)
      - ``text``        — a text overlay (``text`` + ``style``)
      - ``silent_audio``— a silent audio bed (``source``)

    ``box`` (placement rectangle) and ``keyframes`` are reserved for C3+
    (picture-in-picture avatars, ken-burns motion) and unused in C2.
    """

    clip_id: str
    kind: str
    start_s: float = 0.0
    end_s: float = 0.0
    source: AssetRef | None = None
    text: str | None = None
    color: tuple = (0, 0, 0)        # RGB; meaningful for solid_color clips
    style: dict[str, Any] = field(default_factory=dict)
    box: tuple | None = None        # reserved (x, y, w, h) fractions — C3+ PIP
    keyframes: tuple = ()           # reserved — C3+ animation

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class Track:
    """An ordered set of clips of one kind within a scene. Track order is
    z-order for visual tracks (later = on top)."""

    track_id: str
    kind: str                       # "background" | "text" | "audio"
    clips: tuple = ()               # tuple[Clip, ...]


@dataclass(frozen=True)
class Scene:
    """The reusable authoring unit: a slice of the reel with its own layers.

    A C2 scene is a solid background + optional text overlay + a silent audio
    bed, all for ``duration_s`` seconds. ``Scene.simple`` builds exactly that.
    """

    scene_id: str
    index: int
    duration_s: float
    tracks: tuple = ()              # tuple[Track, ...]
    transition_in: Transition = field(default_factory=Transition)
    transition_out: Transition = field(default_factory=Transition)

    # -- convenience accessors used by the renderers (no iteration in callers) --
    def track(self, kind: str) -> Track | None:
        for t in self.tracks:
            if t.kind == kind:
                return t
        return None

    def background_color(self) -> tuple:
        bg = self.track("background")
        if bg and bg.clips:
            return tuple(bg.clips[0].color)
        return (0, 0, 0)

    def text_clips(self) -> tuple:
        t = self.track("text")
        return t.clips if t else ()

    def video_clip(self) -> "Clip | None":
        """The scene's single foreground video clip, if it is a video scene.

        A video scene (see :meth:`from_video`) carries a real talking-head/media
        file on a ``video`` track instead of a synthetic ``solid_color``
        background — this is what lets C3 render generated avatar footage through
        the same Timeline the C2 skeleton rendered solid cards through."""
        vt = self.track("video")
        return vt.clips[0] if (vt and vt.clips) else None

    def audio_file_clip(self) -> "Clip | None":
        """The scene's real (non-silent) audio clip, if any. C3 uses this to mux
        the Voice Engine WAV over the avatar footage; C2 scenes only ever have a
        silent bed and return ``None`` here."""
        at = self.track("audio")
        if at:
            for clip in at.clips:
                if clip.kind == "audio_file":
                    return clip
        return None

    @classmethod
    def from_video(
        cls,
        index: int,
        video_uri: str,
        *,
        duration_s: float,
        audio_uri: str | None = None,
        scene_id: str | None = None,
    ) -> "Scene":
        """Build a one–video(+optional real-audio) scene from generated media.

        This is the C3 counterpart of :meth:`simple`: instead of a synthetic
        solid background it places a real media file (e.g. a talking-head MP4) on
        a ``video`` track that fills the frame, and — when ``audio_uri`` is given
        — the authoritative speech WAV on the ``audio`` track so the renderer
        muxes real audio rather than a silent bed. No overlays, transitions, or
        transforms: it is the minimal video scene that proves the interface.
        """
        sid = scene_id or f"scene-{index:03d}"
        vid_clip = Clip(clip_id=f"{sid}-video", kind="video",
                        start_s=0.0, end_s=duration_s,
                        source=AssetRef(kind="file", uri=video_uri))
        tracks = [Track(track_id=f"{sid}-video-track", kind="video", clips=(vid_clip,))]
        if audio_uri:
            aud_clip = Clip(clip_id=f"{sid}-audio", kind="audio_file",
                            start_s=0.0, end_s=duration_s,
                            source=AssetRef(kind="file", uri=audio_uri))
        else:
            aud_clip = Clip(clip_id=f"{sid}-audio", kind="silent_audio",
                            start_s=0.0, end_s=duration_s,
                            source=AssetRef(kind="silent_audio", uri="generated:silent"))
        tracks.append(Track(track_id=f"{sid}-audio-track", kind="audio", clips=(aud_clip,)))
        return cls(scene_id=sid, index=index, duration_s=duration_s, tracks=tuple(tracks))

    @classmethod
    def simple(
        cls,
        index: int,
        color: tuple,
        text: str | None = None,
        duration_s: float = 3.0,
        *,
        scene_id: str | None = None,
        text_role: str = "title",
        text_style: dict[str, Any] | None = None,
    ) -> "Scene":
        """Build a one-background(+optional-text)+silent-audio scene."""
        sid = scene_id or f"scene-{index:03d}"
        bg_clip = Clip(clip_id=f"{sid}-bg", kind="solid_color",
                       start_s=0.0, end_s=duration_s, color=tuple(color),
                       source=AssetRef(kind="color", uri=_rgb_to_hex(color)))
        tracks = [Track(track_id=f"{sid}-bg-track", kind="background", clips=(bg_clip,))]
        if text:
            style = {"role": text_role, "font_size": 72, "color": "#FFFFFF",
                     "position": "center", **(text_style or {})}
            txt_clip = Clip(clip_id=f"{sid}-text", kind="text",
                            start_s=0.0, end_s=duration_s, text=text, style=style,
                            source=AssetRef(kind="text", uri=text))
            tracks.append(Track(track_id=f"{sid}-text-track", kind="text",
                                clips=(txt_clip,)))
        silent = Clip(clip_id=f"{sid}-audio", kind="silent_audio",
                      start_s=0.0, end_s=duration_s,
                      source=AssetRef(kind="silent_audio", uri="generated:silent"))
        tracks.append(Track(track_id=f"{sid}-audio-track", kind="audio", clips=(silent,)))
        return cls(scene_id=sid, index=index, duration_s=duration_s, tracks=tuple(tracks))


# =========================================================================
# Captions (Phase C4) — a native Timeline track, timed in ABSOLUTE reel time.
#
# Captions are data, not a renderer special-case: the Caption Engine populates
# these frozen types and the renderer simply lowers a CaptionTrack to overlays.
# Everything stays immutable and additive, so v1 timelines are unaffected.
# =========================================================================
@dataclass(frozen=True)
class WordTiming:
    """One word and its absolute time window (for word/karaoke captions)."""

    text: str
    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class CaptionStyle:
    """How captions look. Pure data; the renderer maps it to drawtext options.

    Colours are RGB triples (IR convention). ``font_family`` is a logical name
    the renderer resolves to a font file. Margins are fractions of the frame so
    a style is resolution-independent."""

    name: str = "classic"
    font_family: str = "DejaVuSans"
    font_size: int = 64                    # px at the caption's base resolution
    primary_color: tuple = (255, 255, 255)  # normal word/segment colour (RGB)
    highlight_color: tuple = (255, 215, 0)  # karaoke active-word colour (RGB)
    outline_color: tuple = (0, 0, 0)
    outline_width: int = 4                 # 0 disables the outline
    shadow: bool = True
    shadow_color: tuple = (0, 0, 0)
    shadow_offset: int = 2                 # px; used when shadow is True
    box: bool = False                      # draw a background box behind the text
    box_color: tuple = (0, 0, 0)
    box_opacity: float = 0.5               # 0..1 (only when box is True)
    alignment: str = "center"             # "left" | "center" | "right"
    position: str = "bottom"              # "top" | "center" | "bottom"
    safe_margin_v: float = 0.12            # fraction of height kept clear top+bottom
    safe_margin_h: float = 0.06            # fraction of width kept clear each side
    max_chars_per_line: int = 38
    uppercase: bool = False
    bold: bool = False


@dataclass(frozen=True)
class CaptionAnimation:
    """Simple per-caption animation. C4 keeps it intentionally minimal."""

    kind: str = "none"                     # "none" | "fade" | "pop"
    duration_s: float = 0.2                # lead-in/out length (seconds)


@dataclass(frozen=True)
class CaptionSegment:
    """One on-screen caption (a phrase/sentence) over an absolute time window,
    optionally carrying per-word timings for word/karaoke rendering."""

    segment_id: str
    index: int
    text: str
    start_s: float
    end_s: float
    words: tuple = ()                      # tuple[WordTiming, ...]

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)

    @property
    def has_word_timings(self) -> bool:
        return bool(self.words)


@dataclass(frozen=True)
class CaptionTrack:
    """An ordered set of caption segments plus one shared style + animation.

    ``kind`` selects the presentation the renderer produces:
      - ``sentence`` — one phrase on screen at a time (segment windows)
      - ``static``   — all text shown for the whole track (single card)
      - ``word``     — one word at a time (needs per-word timings)
      - ``karaoke``  — full phrase shown, words highlighted as spoken
    """

    track_id: str
    kind: str = "sentence"                 # "sentence" | "word" | "karaoke" | "static"
    segments: tuple = ()                   # tuple[CaptionSegment, ...] in play order
    style: CaptionStyle = field(default_factory=CaptionStyle)
    animation: CaptionAnimation = field(default_factory=CaptionAnimation)

    @property
    def n_segments(self) -> int:
        return len(self.segments)

    @property
    def duration_s(self) -> float:
        return round(max((s.end_s for s in self.segments), default=0.0), 6)

    def words(self) -> tuple:
        """Flatten every segment's word timings in order (empty if none)."""
        return tuple(w for s in self.segments for w in s.words)


# =========================================================================
# Branding & Theme (Phase C5) — a native Timeline track, timed in ABSOLUTE reel
# time. Branding is data, not a renderer special-case: the Branding Engine
# populates these frozen types (a Theme + typed components) and the renderer
# lowers them to overlays. Everything stays immutable and additive, so v1/v2
# timelines are unaffected.
# =========================================================================
#: The 9-grid + band anchors a branding element may occupy.
BRANDING_POSITIONS = (
    "top_left", "top_center", "top_right",
    "center_left", "center", "center_right",
    "bottom_left", "bottom_center", "bottom_right",
    "bottom",  # full-width lower-third band
)


@dataclass(frozen=True)
class Theme:
    """A reusable visual identity. Pure data; the renderer maps it to overlays.

    Colours are RGB triples; margins are fractions of the frame (resolution
    independent). A Theme supplies the *defaults* every branding component falls
    back to (logo placement, safe area, card/lower-third look, intro/outro
    length), so a creator picks a theme and overrides only what they must."""

    name: str = "classic"
    font_family: str = "DejaVuSans"
    primary_color: tuple = (24, 119, 242)     # brand colour (lower-third band, accents)
    secondary_color: tuple = (255, 255, 255)  # contrast / subtitle colour
    text_color: tuple = (255, 255, 255)       # body text on cards / lower thirds
    background_color: tuple = (12, 14, 20)    # intro/outro card fill
    logo_position: str = "top_right"
    logo_scale: float = 0.14                  # fraction of frame width
    safe_margin_v: float = 0.06               # safe area kept clear top+bottom
    safe_margin_h: float = 0.05               # safe area kept clear each side
    lower_third_position: str = "bottom"
    lower_third_opacity: float = 0.85
    watermark_opacity: float = 0.45
    intro_duration_s: float = 2.0
    outro_duration_s: float = 2.5


@dataclass(frozen=True)
class Logo:
    """A logo image placed on the frame. ``source`` is an image asset; when it
    is absent the renderer draws a text badge from ``text`` (initials/brand)."""

    source: AssetRef | None = None
    text: str | None = None                   # fallback badge text if no image
    position: str = "top_right"
    scale: float = 0.14                       # fraction of frame width
    opacity: float = 1.0
    start_s: float | None = None              # None -> from reel start
    end_s: float | None = None                # None -> to reel end


@dataclass(frozen=True)
class Watermark:
    """A persistent, low-opacity mark (text or image), usually the whole reel."""

    text: str | None = None
    source: AssetRef | None = None
    position: str = "bottom_right"
    scale: float = 0.10
    opacity: float = 0.45
    start_s: float | None = None
    end_s: float | None = None


@dataclass(frozen=True)
class LowerThird:
    """A titled banner (name + role/handle) shown over a time window."""

    title: str
    subtitle: str = ""
    start_s: float = 0.0
    end_s: float = 0.0                        # must be > start_s
    position: str = "bottom"
    opacity: float = 0.85


@dataclass(frozen=True)
class Intro:
    """A full-frame opening card shown for ``duration_s`` from reel start."""

    title: str
    subtitle: str = ""
    duration_s: float = 2.0


@dataclass(frozen=True)
class Outro:
    """A full-frame closing card shown for ``duration_s`` at the reel end,
    optionally listing social handles / a website."""

    title: str
    subtitle: str = ""
    duration_s: float = 2.5
    handles: tuple = ()                       # tuple[str, ...] — handles/website


@dataclass(frozen=True)
class BrandingElement:
    """A resolved, absolutely-timed branding overlay — the generic op the
    renderer consumes (a :class:`BrandingTrack` lowers its typed components to
    these). ``kind`` selects the presentation; unused fields stay defaulted."""

    kind: str                                 # logo|watermark|lower_third|intro|outro
    start_s: float
    end_s: float
    position: str = "center"
    scale: float = 0.14                       # fraction of frame width (logo/watermark)
    opacity: float = 1.0
    text: str | None = None
    subtitle: str | None = None
    lines: tuple = ()                         # extra text lines (outro handles)
    source: AssetRef | None = None            # image asset (logo/watermark)
    fill_color: tuple = (12, 14, 20)          # card / band fill (RGB)
    text_color: tuple = (255, 255, 255)
    font_family: str = "DejaVuSans"
    full_frame: bool = False                  # intro/outro cover the whole frame

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class BrandingTrack:
    """A theme plus its typed branding components — the native branding track.

    All timing is derived at lowering time (intro from reel start, outro from
    reel end, logo/watermark spanning the reel unless bounded), so the track is
    resolution- and duration-agnostic until it meets a concrete Timeline."""

    track_id: str = "branding"
    theme: Theme = field(default_factory=Theme)
    logo: Logo | None = None
    watermark: Watermark | None = None
    intro: Intro | None = None
    outro: Outro | None = None
    lower_thirds: tuple = ()                  # tuple[LowerThird, ...]

    @property
    def has_elements(self) -> bool:
        return any((self.logo, self.watermark, self.intro, self.outro,
                    self.lower_thirds))


@dataclass(frozen=True)
class TimelineMeta:
    """Global, render-relevant metadata. Deliberately free of timestamps or any
    volatile value so the Timeline content hash is stable."""

    title: str = "untitled"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    background_default: tuple = (0, 0, 0)   # RGB used when a scene has no bg

    @property
    def aspect(self) -> str:
        return aspect_ratio_string(self.width, self.height)


@dataclass(frozen=True)
class Timeline:
    """The complete declarative reel: ordered scenes + global metadata.

    ``schema_version`` travels with the object so a loaded old project can be
    migrated. Duration is derived (never stored) so it can't drift from the
    scenes. This whole object is what the renderer lowers to video.
    """

    meta: TimelineMeta = field(default_factory=TimelineMeta)
    scenes: tuple = ()              # tuple[Scene, ...] in play order
    caption_tracks: tuple = ()      # tuple[CaptionTrack, ...] — C4; absolute reel time
    branding: "BrandingTrack | None" = None   # C5; native branding track (absolute time)
    schema_version: int = TIMELINE_SCHEMA_VERSION

    @property
    def duration_s(self) -> float:
        return round(sum(s.duration_s for s in self.scenes), 6)

    @property
    def n_scenes(self) -> int:
        return len(self.scenes)

    @property
    def has_captions(self) -> bool:
        return any(t.segments for t in self.caption_tracks)

    @property
    def has_branding(self) -> bool:
        return self.branding is not None and self.branding.has_elements


@dataclass(frozen=True)
class RenderRequest:
    """One render job: what timeline to render, where, and with which backend."""

    timeline: Timeline
    output_path: Path
    renderer: str = "ffmpeg"        # "ffmpeg" | "mock"
    export_profiles: tuple = ()     # names of export profiles to also emit


@dataclass(frozen=True)
class ExportOutput:
    """One exported file for a specific platform/aspect profile."""

    profile: str
    path: Path
    width: int
    height: int
    aspect: str


@dataclass(frozen=True)
class RenderResult:
    """Outcome of a render: the master file, its measured properties, and any
    per-profile exports. Volatile fields (timings) live here, never in the
    Timeline, so the Timeline hash stays deterministic."""

    output_path: Path
    width: int
    height: int
    fps: float
    duration_s: float
    n_scenes: int
    renderer: str
    render_time_s: float = 0.0
    timeline_hash: str = ""
    exports: tuple = ()             # tuple[ExportOutput, ...]
    audio_path: Path | None = None
    captions_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def aspect(self) -> str:
        return aspect_ratio_string(self.width, self.height)


# --------------------------------------------------------------------- helpers
def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def aspect_ratio_string(width: int, height: int) -> str:
    """Reduced ``W:H`` string, e.g. (1080, 1920) -> ``9:16``."""
    if width <= 0 or height <= 0:
        return "0:0"
    g = _gcd(width, height) or 1
    return f"{width // g}:{height // g}"


def _rgb_to_hex(color: tuple) -> str:
    r, g, b = (int(c) & 0xFF for c in color)
    return f"#{r:02X}{g:02X}{b:02X}"
