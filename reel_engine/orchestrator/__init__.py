"""End-to-end AI Creator Platform orchestration (Phase C3 walking skeleton).

The first complete pipeline through the platform — proving the architecture,
not building the product:

    script text -> Voice Engine -> Avatar Engine -> Timeline IR -> Renderer -> MP4

Reuses the existing engines wholesale (Voice routing, Avatar adapters, the C2
deterministic renderer) behind small stage protocols. Everything is
configuration-driven (:class:`PipelineConfig`); the render backend, models,
resolution, fps, and export set change via YAML/env, never code.

Public API:
- :class:`CreatorPipeline` / :func:`run_pipeline` — orchestration entry points
- :class:`PipelineConfig` / :func:`load_pipeline_config` — layered configuration
- :class:`PipelineResult` — artifacts + per-stage timings
- stage protocols/adapters in :mod:`reel_engine.orchestrator.adapters`
"""
from __future__ import annotations

from reel_engine.orchestrator.adapters import (
    AvatarResult,
    AvatarStage,
    EngineAvatarStage,
    EngineVoiceStage,
    VoiceResult,
    VoiceStage,
)
from reel_engine.orchestrator.config import (
    DEMO_FACE_PATH,
    DEMO_SCRIPT_PATH,
    AvatarStageConfig,
    PipelineConfig,
    VoiceStageConfig,
    load_pipeline_config,
)
from reel_engine.orchestrator.pipeline import (
    CreatorPipeline,
    PipelineError,
    PipelineResult,
    run_pipeline,
)

__all__ = [
    "CreatorPipeline",
    "PipelineResult",
    "PipelineError",
    "run_pipeline",
    "PipelineConfig",
    "VoiceStageConfig",
    "AvatarStageConfig",
    "load_pipeline_config",
    "DEMO_FACE_PATH",
    "DEMO_SCRIPT_PATH",
    "VoiceStage",
    "AvatarStage",
    "VoiceResult",
    "AvatarResult",
    "EngineVoiceStage",
    "EngineAvatarStage",
]
