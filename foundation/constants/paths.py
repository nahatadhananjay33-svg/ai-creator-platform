"""Canonical filesystem locations.

All runtime artifacts (caches, benchmark outputs, downloaded weights) live
under paths defined here so that cleanup, backup, and .gitignore rules stay
in one place.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

FOUNDATION_DIR: Path = PROJECT_ROOT / "foundation"
VOICE_ENGINE_DIR: Path = PROJECT_ROOT / "voice_engine"
AVATAR_ENGINE_DIR: Path = PROJECT_ROOT / "avatar_engine"
DOCS_DIR: Path = PROJECT_ROOT / "docs"

# Runtime (gitignored) locations
CACHE_DIR: Path = FOUNDATION_DIR / "cache" / "data"
MODEL_WEIGHTS_DIR: Path = CACHE_DIR / "model_weights"
BENCHMARK_OUTPUT_DIR: Path = VOICE_ENGINE_DIR / "output" / "runs"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
