"""The deterministic scene planner (Phase C7).

Assembles a finished script into a :class:`Storyboard` by composing the rule
layers in a fixed order:

    segment scenes  ->  per scene: classify -> time -> plan visuals  ->  Storyboard

Every step is pure and rule-based (no model, no I/O, no randomness), so the same
(script, config) always produces an identical storyboard. This is the module the
future AI Script Engine will slot alongside — emitting the same Storyboard shape.
"""
from __future__ import annotations

import re

from scene_engine.config.settings import SceneEngineConfig
from scene_engine.rules.classification import (
    asset_hint,
    classify_scene,
    refine_asset_kind,
)
from scene_engine.rules.profiles import profile_for
from scene_engine.rules.segmentation import segment_scenes
from scene_engine.storyboard.types import (
    AssetSlot,
    AvatarSlot,
    BrandingSlot,
    CaptionSlot,
    NarrationPlan,
    ScenePlan,
    SceneType,
    Storyboard,
    TimingPlan,
    VisualPlan,
)
from scene_engine.timing.estimator import plan_timings

_WORD_RE = re.compile(r"\S+")


def _count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def plan_storyboard(
    script: str,
    cfg: SceneEngineConfig | None = None,
    *,
    title: str = "untitled",
    known_durations: dict[int, float] | None = None,
    creator: str = "",
    channel: str = "",
) -> Storyboard:
    """Plan a :class:`Storyboard` from a finished ``script``.

    ``known_durations`` (scene index -> measured seconds) lets real Voice Engine
    timings replace the estimate for those scenes. ``creator``/``channel`` seed
    the branding slots (lower-third on the hook, outro handles) without any AI.
    """
    cfg = cfg or SceneEngineConfig()

    # 1) Segment into scenes (whole sentences), then classify each.
    scene_sentences = segment_scenes(script, cfg)
    n = len(scene_sentences)
    narrations: list[NarrationPlan] = []
    types: list[SceneType] = []
    for i, sentences in enumerate(scene_sentences):
        text = " ".join(sentences).strip()
        words = _count_words(text)
        narrations.append(NarrationPlan(
            text=text, word_count=words, sentences=tuple(sentences)))
        types.append(classify_scene(
            text, index=i, n_scenes=n, word_count=words,
            explanation_min_words=cfg.explanation_min_words))

    # 2) Time all scenes end-to-end (no gaps/overlaps), reusing known durations.
    timings = plan_timings(
        [(nar.word_count, st) for nar, st in zip(narrations, types)],
        cfg, known_durations=known_durations)

    # 3) Build each scene's visual plan and assemble the ScenePlan.
    scenes: list[ScenePlan] = []
    for i, (nar, st, tm) in enumerate(zip(narrations, types, timings)):
        visual = _plan_visual(i, n, st, nar, tm, cfg,
                              creator=creator, channel=channel)
        scenes.append(ScenePlan(
            scene_id=f"scene-{i:03d}", index=i, scene_type=st,
            narration=nar, timing=tm, visual=visual))

    return Storyboard(scenes=tuple(scenes), title=title,
                      words_per_minute=cfg.words_per_minute)


def _plan_visual(
    index: int,
    n_scenes: int,
    scene_type: SceneType,
    narration: NarrationPlan,
    timing: TimingPlan,
    cfg: SceneEngineConfig,
    *,
    creator: str,
    channel: str,
) -> VisualPlan:
    """Derive the avatar / asset / caption / branding slots for one scene."""
    profile = profile_for(scene_type)
    start, end = timing.start_s, timing.end_s

    avatar = AvatarSlot(
        present=profile.avatar_present,
        layout=(cfg.pip_layout if profile.avatar_layout == "picture_in_picture"
                else "full_screen"),
        start_s=start, end_s=end,
    )

    assets = _plan_assets(index, scene_type, narration.text, profile, timing, cfg)

    caption = CaptionSlot(
        present=True, kind=cfg.caption_kind, preset=cfg.caption_preset,
        start_s=start, end_s=end,
    )

    branding = BrandingSlot(
        logo=True,
        intro=(index == 0),
        outro=(index == n_scenes - 1),
        lower_third=(index == 0 and bool(creator)),
        lower_third_title=creator,
        lower_third_subtitle=channel,
    )

    return VisualPlan(background=profile.background, avatar=avatar,
                      assets=assets, caption=caption, branding=branding)


def _plan_assets(
    index: int,
    scene_type: SceneType,
    text: str,
    profile,
    timing: TimingPlan,
    cfg: SceneEngineConfig,
) -> tuple[AssetSlot, ...]:
    """One :class:`AssetSlot` per asset the profile requests (kinds refined by
    keyword). Comparison scenes get two side-by-side halves. No files touched."""
    if not profile.asset_kinds:
        return ()
    start, end = timing.start_s, timing.end_s
    layout = profile.asset_layout
    if scene_type == SceneType.COMPARISON:
        layout = cfg.comparison_layout
    slots: list[AssetSlot] = []
    for j, base_kind in enumerate(profile.asset_kinds):
        kind = refine_asset_kind(base_kind, text)
        slots.append(AssetSlot(
            slot_id=f"scene-{index:03d}-asset-{j:02d}",
            kind=kind,
            hint=asset_hint(text, kind),
            layout=layout,
            start_s=start, end_s=end,
            required=True,
            z_index=j,
        ))
    return tuple(slots)
