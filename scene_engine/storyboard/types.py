"""Storyboard IR — the frozen contract of the Scene Planning Engine (Phase C7).

A *Storyboard* is the deterministic plan produced from a finished script: an
ordered set of :class:`ScenePlan` beats, each carrying what to say
(:class:`NarrationPlan`), when (:class:`TimingPlan`), and how it should look
(:class:`VisualPlan` — an avatar slot, asset slots, a caption slot, a branding
slot). It is *plan data*, not rendered pixels and not retrieved assets: an
:class:`AssetSlot` is a **request** the Visual Asset Engine satisfies later; the
storyboard never touches the filesystem or a network.

This is also the format a later **AI Script Engine** will emit, so the shape is
frozen and forward-compatible: everything is an immutable
``@dataclass(frozen=True)`` with tuple collections, exactly like the Timeline IR
in ``reel_engine.interfaces``. The planner (rules) fills these; the timeline
builder lowers them to the existing Timeline IR; the renderer is untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

#: Bumped whenever the Storyboard schema changes incompatibly. It travels with a
#: :class:`Storyboard` so a persisted plan can be validated/migrated later.
STORYBOARD_SCHEMA_VERSION = 1


class SceneType(str, Enum):
    """The deterministic scene classes the planner assigns.

    A ``str`` enum so a scene type is JSON-friendly and compares equal to its
    wire value (``SceneType.HOOK == "hook"``) while still being a typed member.
    The set is closed — classification is rules-only, never a model.
    """

    HOOK = "hook"
    TALKING_HEAD = "talking_head"
    EXPLANATION = "explanation"
    IMAGE_INSERT = "image_insert"
    VIDEO_INSERT = "video_insert"
    COMPARISON = "comparison"
    BULLET_LIST = "bullet_list"
    CHART = "chart"
    QUOTE = "quote"
    CALL_TO_ACTION = "call_to_action"
    OUTRO = "outro"

    @property
    def label(self) -> str:
        """Human-readable name, e.g. ``SceneType.CALL_TO_ACTION`` -> ``Call To Action``."""
        return self.value.replace("_", " ").title()


#: All scene-type wire values, in declaration order (stable for reporting/tests).
SCENE_TYPES: tuple[str, ...] = tuple(t.value for t in SceneType)

#: The visual-asset kinds a scene may *request*. A superset hint the Asset Engine
#: later resolves; ``"logo"`` is a branding element (resolved by the Branding
#: Engine), carried here so the plan is complete. The image-like kinds map onto
#: ``reel_engine`` ``ASSET_KINDS`` when a slot is lowered to an ``AssetSpec``.
SLOT_KINDS: tuple[str, ...] = (
    "image", "video", "chart", "map", "screenshot", "document",
    "icon", "illustration", "logo",
)


@dataclass(frozen=True)
class NarrationPlan:
    """What the scene says: the narration text plus its sentence breakdown.

    ``text`` is the exact spoken copy (the Voice Engine synthesizes it later);
    ``sentences`` are the segmented sentences that fell into this scene. Word
    count is stored (not recomputed) so timing and mix stats stay consistent.
    """

    text: str
    word_count: int
    sentences: tuple[str, ...] = ()

    @property
    def n_sentences(self) -> int:
        return len(self.sentences)


@dataclass(frozen=True)
class TimingPlan:
    """When the scene plays, in ABSOLUTE reel time (seconds).

    ``speech_duration_s`` is the estimated narration length; ``start_s``/``end_s``
    are the contiguous scene window (``end_s`` may exceed speech when a floor or a
    preferred CTA/outro length pads it). Transitions are carried for later phases
    (C7 defaults to hard cuts, ``0.0``)."""

    start_s: float
    end_s: float
    speech_duration_s: float
    transition_in_s: float = 0.0
    transition_out_s: float = 0.0

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class AvatarSlot:
    """Whether/how the talking-head avatar appears in the scene.

    ``layout`` is ``full_screen`` (avatar is the whole frame) or
    ``picture_in_picture`` (avatar insets while a B-roll asset fills the frame).
    Timed in absolute reel time so it maps straight to the avatar/asset tracks."""

    present: bool = True
    layout: str = "full_screen"          # full_screen | picture_in_picture
    start_s: float = 0.0
    end_s: float = 0.0

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class AssetSlot:
    """A REQUEST for one visual asset — never a retrieved file.

    The planner emits slots (need a chart here, an image there); the Visual Asset
    Engine satisfies them in a later phase. ``hint`` is a deterministic,
    keyword-derived description (no AI). ``layout`` is a preferred
    ``reel_engine`` asset layout; the window is absolute reel time."""

    slot_id: str
    kind: str                            # one of SLOT_KINDS
    hint: str = ""
    layout: str = "full_screen"          # a reel_engine ASSET_LAYOUTS value
    start_s: float = 0.0
    end_s: float = 0.0
    required: bool = True
    z_index: int = 0

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 6)


@dataclass(frozen=True)
class CaptionSlot:
    """The scene's caption intent — kind + style preset + window.

    The timeline builder turns this (plus the narration) into a native
    ``CaptionTrack`` segment; the Caption Engine owns styling."""

    present: bool = True
    kind: str = "sentence"               # sentence | word | karaoke | static
    preset: str = "clean"                # caption style preset name
    start_s: float = 0.0
    end_s: float = 0.0


@dataclass(frozen=True)
class BrandingSlot:
    """The scene's branding intent (resolved by the Branding Engine later).

    Intro is set on the first scene, outro on the last; a persistent logo and an
    optional lower-third (e.g. the creator name over the hook) are flags the
    branding track reads."""

    logo: bool = True
    intro: bool = False
    outro: bool = False
    lower_third: bool = False
    lower_third_title: str = ""
    lower_third_subtitle: str = ""


@dataclass(frozen=True)
class VisualPlan:
    """How the scene looks: a background hint + the four typed slots.

    Groups the visual planning for one scene so the timeline builder has a single
    place to read from. ``background`` is an RGB hint used for the scene's solid
    card (the deterministic stand-in until real avatar/B-roll footage lands)."""

    background: tuple = (0, 0, 0)        # RGB scene background hint
    avatar: AvatarSlot = field(default_factory=AvatarSlot)
    assets: tuple[AssetSlot, ...] = ()
    caption: CaptionSlot = field(default_factory=CaptionSlot)
    branding: BrandingSlot = field(default_factory=BrandingSlot)

    @property
    def has_assets(self) -> bool:
        return bool(self.assets)

    @property
    def primary_layout(self) -> str:
        """The dominant on-screen layout: the first asset's layout, else the
        avatar layout (what fills the frame when no B-roll is requested)."""
        return self.assets[0].layout if self.assets else self.avatar.layout


@dataclass(frozen=True)
class ScenePlan:
    """One planned scene: type + narration + timing + visual plan."""

    scene_id: str
    index: int
    scene_type: SceneType
    narration: NarrationPlan
    timing: TimingPlan
    visual: VisualPlan

    @property
    def duration_s(self) -> float:
        return self.timing.duration_s

    @property
    def start_s(self) -> float:
        return self.timing.start_s

    @property
    def end_s(self) -> float:
        return self.timing.end_s


@dataclass(frozen=True)
class Storyboard:
    """The complete deterministic plan: ordered scenes + metadata.

    Duration is derived (never stored) so it can't drift from the scenes. This is
    what the timeline builder lowers into the existing Timeline IR, and the shape
    a future AI Script Engine will emit.
    """

    scenes: tuple[ScenePlan, ...] = ()
    title: str = "untitled"
    words_per_minute: float = 150.0
    schema_version: int = STORYBOARD_SCHEMA_VERSION

    @property
    def n_scenes(self) -> int:
        return len(self.scenes)

    @property
    def duration_s(self) -> float:
        return round(sum(s.duration_s for s in self.scenes), 6)

    @property
    def word_count(self) -> int:
        return sum(s.narration.word_count for s in self.scenes)

    @property
    def all_asset_slots(self) -> tuple[AssetSlot, ...]:
        """Every asset slot across every scene, in play order."""
        return tuple(a for s in self.scenes for a in s.visual.assets)

    def scene_types(self) -> tuple[SceneType, ...]:
        return tuple(s.scene_type for s in self.scenes)

    def type_mix(self) -> dict[str, float]:
        """Fraction of total reel time spent in each scene type (for reporting
        and the preferred-mix soft checks). Empty for an empty storyboard."""
        total = self.duration_s
        if total <= 0:
            return {}
        mix: dict[str, float] = {}
        for s in self.scenes:
            mix[s.scene_type.value] = mix.get(s.scene_type.value, 0.0) + s.duration_s
        return {k: round(v / total, 6) for k, v in mix.items()}
