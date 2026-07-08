"""Content hashing for the Timeline IR (Phase C2).

Every Timeline (and every Scene) hashes to a stable digest of its *structural*
content — the basis for the render cache, scene reuse, and reproducibility in
later phases. The hash is taken over canonical JSON (sorted keys, no whitespace
variance), and the Timeline schema carries **no** volatile fields (timestamps,
timings), so the same reel always hashes the same.
"""
from __future__ import annotations

import json

from foundation.shared_utils.hashing import sha256_text
from reel_engine.interfaces.types import Scene, Timeline
from reel_engine.timeline.serde import _scene_to_dict, timeline_to_dict


def canonical_json(obj) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8 preserved."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def timeline_content_hash(tl: Timeline) -> str:
    """SHA-256 hex of a Timeline's structural content (stable across serde)."""
    return sha256_text(canonical_json(timeline_to_dict(tl)))


def scene_content_hash(scene: Scene) -> str:
    """SHA-256 hex of one Scene — the future per-scene render-cache key."""
    return sha256_text(canonical_json(_scene_to_dict(scene)))
