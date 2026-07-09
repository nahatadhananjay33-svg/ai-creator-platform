"""Creator Studio panel builders (Phase C12) — pure view-model projections.

Each function turns engine-owned state (a :class:`ReelProject`, its lowered
:class:`Timeline`, an :class:`EditHistory`, an :class:`IncrementalPlan`) into a
frozen view model from :mod:`creator_studio.viewmodels`. They are **pure**: no
mutation, no I/O, no patch construction, no randomness — the same inputs always
produce the same panel, which is what makes the UI hermetically testable.

All editing logic stays in the Editing Engine; these builders only *read* and
*format* what the engine already computed.
"""
from __future__ import annotations

from editing_engine.history.history import EditHistory
from editing_engine.incremental import IncrementalPlan
from editing_engine.patches.base import (
    VALID_ASSET_KINDS,
    VALID_ASSET_LAYOUTS,
    VALID_SCENE_TYPES,
    valid_caption_kinds,
    valid_caption_styles,
    valid_soundtracks,
    valid_themes,
)
from editing_engine.project import ReelProject
from reel_engine.interfaces.types import Timeline, aspect_ratio_string

from creator_studio.viewmodels import (
    HistoryEntry,
    HistoryPanel,
    IncrementalPanel,
    InspectorPanel,
    PreviewPanel,
    ProjectInfo,
    SceneRow,
    StoryboardPanel,
    TimelineBar,
    TimelinePanel,
)

#: How many characters of narration a compact scene row shows.
_PREVIEW_CHARS = 60


def _truncate(text: str, limit: int = _PREVIEW_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def scene_offsets(timeline: Timeline) -> tuple[float, ...]:
    """Absolute start time of every rendered scene (for playhead seeking)."""
    offsets: list[float] = []
    t = 0.0
    for scene in timeline.scenes:
        offsets.append(round(t, 6))
        t += scene.duration_s
    return tuple(offsets)


def scene_at_time(timeline: Timeline, t: float) -> int:
    """Index of the rendered scene containing absolute time ``t`` (clamped)."""
    if not timeline.scenes:
        return 0
    acc = 0.0
    for i, scene in enumerate(timeline.scenes):
        acc += scene.duration_s
        if t < acc - 1e-9:
            return i
    return len(timeline.scenes) - 1


# ------------------------------------------------------------------ panels
def build_project_info(project: ReelProject, *, base_revision: int,
                       duration_s: float, dirty: bool, path: str | None) -> ProjectInfo:
    return ProjectInfo(
        title=project.storyboard.title,
        revision=project.revision,
        base_revision=base_revision,
        n_scenes=project.n_scenes,
        duration_s=round(duration_s, 3),
        theme=project.theme,
        soundtrack=project.soundtrack,
        caption_kind=project.caption_kind,
        caption_preset=project.caption_preset,
        width=project.width,
        height=project.height,
        fps=project.fps,
        dirty=dirty,
        path=path,
        provider=project.storyboard.provider,
    )


def build_storyboard_panel(project: ReelProject, selected: int) -> StoryboardPanel:
    rows = tuple(
        SceneRow(
            index=i,
            narration=s.narration,
            preview=_truncate(s.narration),
            scene_type=s.scene_type,
            asset_type=s.asset_type,
            layout=s.layout,
            duration_estimate_s=s.duration_estimate_s,
            word_count=s.word_count,
            cta=s.cta,
            selected=(i == selected),
        )
        for i, s in enumerate(project.scenes)
    )
    return StoryboardPanel(scenes=rows, n_scenes=len(rows), selected_index=selected)


def build_timeline_panel(timeline: Timeline, *, selected_scene: int, playhead_s: float,
                         plan: IncrementalPlan | None) -> TimelinePanel:
    changed = set(plan.changed) if plan else set()
    reused = set(plan.reused) if plan else set()
    cacheable = set(plan.cacheable) if plan else set()
    offsets = scene_offsets(timeline)
    bars: list[TimelineBar] = []
    for i, scene in enumerate(timeline.scenes):
        if plan is None:
            status = "base"
        elif i in reused:
            status = "reused"
        elif i in changed:
            status = "changed"
        else:
            status = "base"
        bars.append(TimelineBar(
            index=i,
            scene_id=scene.scene_id,
            start_s=offsets[i],
            end_s=round(offsets[i] + scene.duration_s, 6),
            duration_s=scene.duration_s,
            status=status,
            cacheable=(i in cacheable),
            selected=(i == selected_scene),
        ))
    meta = timeline.meta
    return TimelinePanel(
        bars=tuple(bars),
        total_duration_s=timeline.duration_s,
        playhead_s=round(playhead_s, 6),
        playhead_scene=scene_at_time(timeline, playhead_s),
        fps=meta.fps,
        width=meta.width,
        height=meta.height,
        aspect=aspect_ratio_string(meta.width, meta.height),
    )


def build_inspector_panel(project: ReelProject, selected: int,
                          captions_enabled: bool) -> InspectorPanel:
    scenes = project.scenes
    idx = selected if 0 <= selected < len(scenes) else (0 if scenes else -1)
    scene = scenes[idx] if scenes else None
    return InspectorPanel(
        scene_index=idx,
        narration=scene.narration if scene else "",
        duration_estimate_s=scene.duration_estimate_s if scene else 0.0,
        scene_type=scene.scene_type if scene else "",
        asset_type=scene.asset_type if scene else "",
        layout=scene.layout if scene else "",
        theme=project.theme,
        soundtrack=project.soundtrack,
        caption_kind=project.caption_kind,
        caption_preset=project.caption_preset,
        captions_enabled=captions_enabled,
        theme_options=valid_themes(),
        soundtrack_options=valid_soundtracks(),
        caption_kind_options=valid_caption_kinds(),
        caption_preset_options=valid_caption_styles(),
        asset_kind_options=VALID_ASSET_KINDS,
        asset_layout_options=VALID_ASSET_LAYOUTS,
        scene_type_options=VALID_SCENE_TYPES,
    )


def build_incremental_panel(plan: IncrementalPlan | None) -> IncrementalPanel:
    if plan is None:
        return IncrementalPanel(
            total=0, changed=(), reused=(), cacheable=(), overlays_changed=False,
            needs_render=False, reuse_fraction=1.0, n_changed=0, n_reused=0,
            scene_status=(), cache_hits=0, cache_misses=0, cacheable_hits=0)
    reused = set(plan.reused)
    status = tuple("reused" if i in reused else "changed" for i in range(plan.total))
    return IncrementalPanel(
        total=plan.total,
        changed=plan.changed,
        reused=plan.reused,
        cacheable=plan.cacheable,
        overlays_changed=plan.overlays_changed,
        needs_render=plan.needs_render,
        reuse_fraction=plan.reuse_fraction,
        n_changed=plan.n_changed,
        n_reused=plan.n_reused,
        scene_status=status,
        cache_hits=plan.n_reused,
        cache_misses=plan.n_changed,
        cacheable_hits=len(plan.cacheable),
    )


def build_history_panel(history: EditHistory) -> HistoryPanel:
    cursor = history.n_patches - 1
    entries = tuple(
        HistoryEntry(revision=i + 1, op=p.op, describe=p.describe(),
                     current=(i == cursor))
        for i, p in enumerate(history.patches)
    )
    return HistoryPanel(
        entries=entries,
        can_undo=history.can_undo,
        can_redo=history.can_redo,
        n_patches=history.n_patches,
        cursor=cursor,
    )


def build_preview_panel(*, media_path: str | None, audio_path: str | None,
                        captions_path: str | None, renderer: str, timeline: Timeline,
                        playhead_s: float, playing: bool, ready: bool) -> PreviewPanel:
    return PreviewPanel(
        media_path=media_path,
        audio_path=audio_path,
        captions_path=captions_path,
        renderer=renderer,
        duration_s=timeline.duration_s,
        playhead_s=round(playhead_s, 6),
        playing=playing,
        current_scene=scene_at_time(timeline, playhead_s),
        scene_offsets=scene_offsets(timeline),
        ready=ready,
    )
