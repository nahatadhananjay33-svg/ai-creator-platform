"""Storyboard <-> plain-dict serialization (Phase C7).

A tiny, dependency-free serializer so a :class:`Storyboard` can be written to
JSON (the demo dumps ``storyboard.json`` next to the render). It is deterministic
— keys are emitted in a fixed order — so the same plan always yields byte-
identical JSON, which keeps the hermetic tests and any caching reproducible.

This is NOT the Timeline serde (that lives in ``reel_engine.timeline.serde``);
this only round-trips the plan, which upstream/downstream tools can inspect.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from scene_engine.storyboard.types import (
    STORYBOARD_SCHEMA_VERSION,
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


def storyboard_to_dict(sb: Storyboard) -> dict:
    """Convert a :class:`Storyboard` to JSON-serializable plain dicts.

    ``dataclasses.asdict`` would leave :class:`SceneType` as an enum member (not
    JSON serializable), so scenes are converted explicitly with the enum lowered
    to its wire value.
    """
    return {
        "title": sb.title,
        "schema_version": sb.schema_version,
        "words_per_minute": sb.words_per_minute,
        "duration_s": sb.duration_s,
        "n_scenes": sb.n_scenes,
        "word_count": sb.word_count,
        "type_mix": sb.type_mix(),
        "scenes": [_scene_to_dict(s) for s in sb.scenes],
    }


def storyboard_to_json(sb: Storyboard, *, indent: int = 2) -> str:
    return json.dumps(storyboard_to_dict(sb), indent=indent, ensure_ascii=False)


def storyboard_from_dict(data: dict) -> Storyboard:
    """Rebuild a :class:`Storyboard` from :func:`storyboard_to_dict` output."""
    scenes = tuple(_scene_from_dict(s) for s in data.get("scenes", ()))
    return Storyboard(
        scenes=scenes,
        title=data.get("title", "untitled"),
        words_per_minute=data.get("words_per_minute", 150.0),
        schema_version=data.get("schema_version", STORYBOARD_SCHEMA_VERSION),
    )


# --------------------------------------------------------------------- helpers
def _scene_to_dict(s: ScenePlan) -> dict:
    d = asdict(s)
    d["scene_type"] = s.scene_type.value        # enum -> wire value
    return d


def _scene_from_dict(d: dict) -> ScenePlan:
    n = d["narration"]
    t = d["timing"]
    v = d["visual"]
    return ScenePlan(
        scene_id=d["scene_id"],
        index=d["index"],
        scene_type=SceneType(d["scene_type"]),
        narration=NarrationPlan(
            text=n["text"], word_count=n["word_count"],
            sentences=tuple(n.get("sentences", ()))),
        timing=TimingPlan(**t),
        visual=VisualPlan(
            background=tuple(v.get("background", (0, 0, 0))),
            avatar=AvatarSlot(**v["avatar"]),
            assets=tuple(AssetSlot(**a) for a in v.get("assets", ())),
            caption=CaptionSlot(**v["caption"]),
            branding=BrandingSlot(**v["branding"]),
        ),
    )
