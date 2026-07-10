"""Workflow Engine integration (Phase C16) — quality-gate a finished run.

This is the bridge between the Quality Checker and the C14 Workflow Engine. It
reads a standard :class:`WorkflowResult` (the outcome of the ``prompt -> export``
pipeline), assembles a :class:`ReelArtifacts` from the run's own artifacts — the
rendered master + exports, the Timeline it was rendered from, the voice clips, the
avatar plan — and returns a :class:`QualityReport`.

It **changes no engine**: no renderer, no Timeline, no stage. It only *reads* the
artifacts the run already produced, so it slots in strictly after the render/export
stages as a pure, side-effect-free gate:

    Workflow Engine -> Render -> Export -> Quality Check -> PASS | FAIL
"""
from __future__ import annotations

from pathlib import Path

from workflow_engine.core.workflow import WorkflowResult

from quality_engine.checker.config import QualityConfig
from quality_engine.checker.engine import QualityChecker
from quality_engine.checker.model import ExportInfo, ReelArtifacts
from quality_engine.checker.report import QualityReport


def artifacts_from_result(result: WorkflowResult) -> ReelArtifacts:
    """Build :class:`ReelArtifacts` from a workflow run's artifacts.

    Tolerant of a trimmed pipeline: any missing artifact (timeline/voice/avatar)
    simply degrades the corresponding check to a warning/skip rather than raising.
    """
    arts = result.artifacts
    master = arts["master"]                      # required — the render output
    master_path = Path(master.value or master.path)

    exports = tuple(
        ExportInfo(profile=e.get("profile", ""), path=Path(e["path"]),
                   width=e.get("width", 0), height=e.get("height", 0),
                   aspect=e.get("aspect", ""))
        for e in master.meta.get("exports", [])
    )

    timeline_art = arts.get("timeline")
    timeline = timeline_art.value if timeline_art is not None else None

    voice_art = arts.get("voice")
    voice_clips = tuple(voice_art.value) if (voice_art and voice_art.value) else ()

    avatar_art = arts.get("avatar")
    avatar = avatar_art.value if (avatar_art and isinstance(avatar_art.value, dict)) else None

    # The mock renderer writes audio/caption sidecars next to the master; the
    # ffmpeg backend muxes/burns them in (checker falls back to the Timeline).
    audio_sidecar = master_path.with_suffix(".wav")
    caption_sidecar = master_path.with_suffix(".srt")

    return ReelArtifacts(
        master_path=master_path, timeline=timeline,
        audio_path=audio_sidecar if audio_sidecar.exists() else None,
        captions_path=caption_sidecar if caption_sidecar.exists() else None,
        exports=exports, voice_clips=voice_clips, avatar=avatar,
        renderer=master.meta.get("renderer", "mock"),
    )


def check_workflow_result(result: WorkflowResult, *,
                          config: QualityConfig | None = None) -> QualityReport:
    """Quality-check the reel a workflow run produced."""
    return QualityChecker(config).check(artifacts_from_result(result))
