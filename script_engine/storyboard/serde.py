"""AIStoryboard <-> plain-dict/JSON serialization (Phase C10).

A tiny, dependency-free serializer. Deterministic field order, so the same brief
always serializes byte-identically (keeps hermetic tests and caching stable).
``from_dict`` is also how a real LLM provider's JSON response is rebuilt into an
:class:`AIStoryboard` — the wire shape is exactly :data:`AI_STORYBOARD_JSON_SCHEMA`.
"""
from __future__ import annotations

import json

from script_engine.storyboard.types import (
    SCRIPT_SCHEMA_VERSION,
    AIStoryboard,
    ScriptScene,
)


def scene_to_dict(s: ScriptScene) -> dict:
    return {
        "narration": s.narration, "scene_type": s.scene_type,
        "asset_type": s.asset_type, "layout": s.layout, "cta": s.cta,
        "duration_estimate_s": s.duration_estimate_s, "keywords": list(s.keywords),
    }


def storyboard_to_dict(sb: AIStoryboard) -> dict:
    return {
        "schema_version": sb.schema_version,
        "title": sb.title, "target_audience": sb.target_audience, "tone": sb.tone,
        "hook": sb.hook, "language": sb.language, "template": sb.template,
        "provider": sb.provider, "model": sb.model, "prompt": sb.prompt,
        "n_scenes": sb.n_scenes, "word_count": sb.word_count,
        "scenes": [scene_to_dict(s) for s in sb.scenes],
    }


def storyboard_to_json(sb: AIStoryboard, *, indent: int | None = 2) -> str:
    return json.dumps(storyboard_to_dict(sb), indent=indent, ensure_ascii=False)


def scene_from_dict(d: dict) -> ScriptScene:
    return ScriptScene(
        narration=d.get("narration", ""),
        scene_type=d.get("scene_type", "explanation"),
        asset_type=d.get("asset_type", ""), layout=d.get("layout", ""),
        cta=bool(d.get("cta", False)),
        duration_estimate_s=float(d.get("duration_estimate_s", 0.0) or 0.0),
        keywords=tuple(d.get("keywords", ()) or ()),
    )


def storyboard_from_dict(d: dict, *, provider: str = "", model: str = "",
                         prompt: str = "", template: str = "general",
                         language: str = "en") -> AIStoryboard:
    """Rebuild an :class:`AIStoryboard` from a mapping (e.g. an LLM JSON response).

    Provenance fields (provider/model/prompt/template/language) default to the
    caller's values but are overridden by the mapping when present, so both a
    provider response (no provenance) and a serialized round-trip work."""
    return AIStoryboard(
        title=d.get("title", "Untitled"),
        scenes=tuple(scene_from_dict(s) for s in d.get("scenes", ())),
        target_audience=d.get("target_audience", "general audience"),
        tone=d.get("tone", "informative"),
        hook=d.get("hook", ""),
        prompt=d.get("prompt", prompt),
        template=d.get("template", template),
        language=d.get("language", language),
        provider=d.get("provider", provider),
        model=d.get("model", model),
        schema_version=d.get("schema_version", SCRIPT_SCHEMA_VERSION),
    )


def storyboard_from_json(text: str, **provenance) -> AIStoryboard:
    return storyboard_from_dict(json.loads(text), **provenance)
