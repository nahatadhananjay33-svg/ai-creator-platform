"""Timeline serialization + content-hashing tests (Phase C2). Hermetic."""
from __future__ import annotations

import json

import pytest

from reel_engine.interfaces import TIMELINE_SCHEMA_VERSION
from reel_engine.timeline import (
    build_demo_timeline,
    canonical_json,
    scene_content_hash,
    timeline_content_hash,
    timeline_from_dict,
    timeline_from_json,
    timeline_to_dict,
    timeline_to_json,
)


def test_json_roundtrip_is_lossless():
    tl = build_demo_timeline()
    restored = timeline_from_json(timeline_to_json(tl))
    # structural equality via canonical dicts (frozen dataclasses compare by value)
    assert timeline_to_dict(restored) == timeline_to_dict(tl)
    assert restored == tl


def test_serialized_form_carries_schema_version():
    tl = build_demo_timeline()
    d = json.loads(timeline_to_json(tl))
    assert d["schema_version"] == TIMELINE_SCHEMA_VERSION
    assert d["meta"]["width"] == 1080 and len(d["scenes"]) == 3


def test_loader_rejects_future_schema_version():
    d = timeline_to_dict(build_demo_timeline())
    d["schema_version"] = TIMELINE_SCHEMA_VERSION + 1
    with pytest.raises(ValueError):
        timeline_from_dict(d)


def test_content_hash_is_deterministic_and_serde_stable():
    tl = build_demo_timeline()
    h = timeline_content_hash(tl)
    assert h == timeline_content_hash(build_demo_timeline())          # rebuild
    assert h == timeline_content_hash(timeline_from_json(timeline_to_json(tl)))  # round-trip
    assert len(h) == 64  # sha256 hex


def test_content_hash_changes_with_content():
    base = timeline_content_hash(build_demo_timeline())
    assert base != timeline_content_hash(build_demo_timeline(fps=60))
    assert base != timeline_content_hash(build_demo_timeline(duration_s=3.0))
    assert base != timeline_content_hash(build_demo_timeline(width=1080, height=1080))


def test_scene_hash_distinguishes_scenes():
    tl = build_demo_timeline()
    hashes = [scene_content_hash(s) for s in tl.scenes]
    assert len(set(hashes)) == 3  # blue/green/red scenes are distinct


def test_canonical_json_is_sorted_and_compact():
    s = canonical_json({"b": 1, "a": 2})
    assert s == '{"a":2,"b":1}'
