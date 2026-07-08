"""End-to-end AI Creator Platform pipeline (Phase C3 walking skeleton).

The first complete path through the platform, proving the architecture — nothing
more:

    script text -> Voice Engine -> Avatar Engine -> Timeline IR -> Renderer -> MP4

One scene, no captions/planning/b-roll/music/branding/transitions (C4+). Every
stage is timed; the assembled Timeline is validated and serialized to a
``project.json`` (the resumable anchor later phases build on); the renderer is
the deterministic C2 backend, now able to lower a video scene (Phase C3/M1).

Stages are injected through the :mod:`~reel_engine.orchestrator.adapters`
protocols, so the whole orchestration is testable with deterministic fakes and
no model weights; the real path wires the production Voice/Avatar engines.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from foundation.exceptions import PlatformError
from foundation.logging import get_logger
from foundation.shared_utils import Stopwatch

from reel_engine.interfaces.types import (
    ExportOutput,
    RenderRequest,
    RenderResult,
    Scene,
    Timeline,
)
from reel_engine.orchestrator.adapters import (
    AvatarResult,
    AvatarStage,
    EngineAvatarStage,
    EngineVoiceStage,
    VoiceResult,
    VoiceStage,
)
from reel_engine.orchestrator.config import PipelineConfig
from reel_engine.render import get_renderer
from reel_engine.timeline.model import new_timeline
from reel_engine.timeline.serde import timeline_to_json

logger = get_logger("reel_engine.orchestrator.pipeline")


class PipelineError(PlatformError):
    """The end-to-end pipeline could not produce a reel."""


@dataclass(frozen=True)
class PipelineResult:
    """Everything the pipeline produced plus per-stage timings."""

    output_path: Path                       # the master reel MP4
    project_path: Path                      # serialized Timeline (project.json)
    audio_path: Path                        # Voice Engine WAV
    avatar_path: Path                       # Avatar Engine talking-head video
    timeline: Timeline
    render: RenderResult
    voice: VoiceResult
    avatar: AvatarResult
    exports: tuple = ()                     # tuple[ExportOutput, ...]
    timings: dict = field(default_factory=dict)   # stage -> seconds

    @property
    def width(self) -> int:
        return self.render.width

    @property
    def height(self) -> int:
        return self.render.height

    @property
    def fps(self) -> float:
        return self.render.fps

    @property
    def duration_s(self) -> float:
        return self.render.duration_s


class CreatorPipeline:
    """Orchestrates the five stages into one reel."""

    def __init__(
        self,
        config: PipelineConfig,
        *,
        voice_stage: VoiceStage | None = None,
        avatar_stage: AvatarStage | None = None,
    ) -> None:
        self.config = config
        self.voice_stage = voice_stage or EngineVoiceStage(config.voice)
        self.avatar_stage = avatar_stage or EngineAvatarStage(config.avatar)

    # --------------------------------------------------------------- run
    def run(
        self,
        *,
        script: str | None = None,
        script_path: Path | str | None = None,
        reference: Path | str | None = None,
        output_name: str = "reel",
    ) -> PipelineResult:
        """Generate one reel from a text script and a reference face/video."""
        text = self._read_script(script, script_path)
        reference_path = Path(reference) if reference else self.config.resolved_reference()
        if not reference_path.exists():
            raise PipelineError("Reference face/video not found",
                                reference=str(reference_path))

        workdir = self.config.resolved_output_dir() / output_name
        workdir.mkdir(parents=True, exist_ok=True)
        logger.info("Pipeline start", extra={"context": {
            "voice": self.config.voice.model, "avatar": self.config.avatar.model,
            "renderer": self.config.render.renderer, "chars": len(text)}})

        timings: dict[str, float] = {}
        with Stopwatch() as total:
            # 1. Voice: text -> speech WAV
            with Stopwatch() as sw:
                voice = self.voice_stage.synthesize(text, workdir / "speech.wav")
            timings["voice_s"] = round(sw.elapsed_s, 4)

            # 2. Avatar: (reference, speech) -> talking-head video
            with Stopwatch() as sw:
                avatar = self.avatar_stage.generate(
                    reference_path, voice.audio_path, workdir / "avatar.mp4")
            timings["avatar_s"] = round(sw.elapsed_s, 4)

            # 3. Timeline: wrap the footage + speech into a validated single-scene IR
            with Stopwatch() as sw:
                timeline = self._build_timeline(avatar, voice)
                project_path = workdir / "project.json"
                project_path.write_text(timeline_to_json(timeline), encoding="utf-8")
            timings["timeline_s"] = round(sw.elapsed_s, 4)

            # 4. Render master + 5. Export profiles (timed separately)
            master, exports, render_s, export_s = self._render(
                timeline, workdir / f"{output_name}.mp4")
            timings["render_s"] = round(render_s, 4)
            timings["export_s"] = round(export_s, 4)

        timings["total_s"] = round(total.elapsed_s, 4)
        logger.info("Pipeline done", extra={"context": {
            "output": str(master.output_path), "duration_s": master.duration_s,
            "total_s": timings["total_s"]}})

        return PipelineResult(
            output_path=master.output_path, project_path=project_path,
            audio_path=voice.audio_path, avatar_path=avatar.video_path,
            timeline=timeline, render=master, voice=voice, avatar=avatar,
            exports=tuple(exports), timings=timings,
        )

    # ----------------------------------------------------------- internals
    @staticmethod
    def _read_script(script: str | None, script_path: Path | str | None) -> str:
        if script is not None:
            text = script
        elif script_path is not None:
            path = Path(script_path)
            if not path.exists():
                raise PipelineError("Script file not found", path=str(path))
            text = path.read_text(encoding="utf-8")
        else:
            raise PipelineError("No script provided (pass script= or script_path=)")
        text = text.strip()
        if not text:
            raise PipelineError("Script is empty")
        return text

    def _build_timeline(self, avatar: AvatarResult, voice: VoiceResult) -> Timeline:
        """One video scene: the talking head + the authoritative speech WAV.

        Scene length follows the generated footage; the renderer trims to the
        shorter of footage/audio so a small voice/avatar mismatch can't overrun.
        """
        r = self.config.render
        scene = Scene.from_video(
            index=0,
            video_uri=str(avatar.video_path),
            duration_s=round(avatar.duration_s, 3),
            audio_uri=str(voice.audio_path),
        )
        return new_timeline([scene], title="AI Creator Platform reel",
                            width=r.width, height=r.height, fps=r.fps)

    def _render(self, timeline: Timeline, master_path: Path):
        """Render the master, then export profiles from it — timed separately."""
        reel_cfg = self.config.reel_config()
        backend = self.config.render.renderer
        profiles = tuple(self.config.export.profiles)
        renderer = get_renderer(backend, reel_cfg)

        with Stopwatch() as rsw:
            master = renderer.render(RenderRequest(
                timeline=timeline, output_path=master_path,
                renderer=backend, export_profiles=()))

        exports: tuple = ()
        with Stopwatch() as esw:
            if profiles:
                if hasattr(renderer, "export_master"):
                    exports = renderer.export_master(master.output_path, profiles)
                else:
                    # Backends without master-export re-render with profiles; only
                    # the exports are kept (the master above is authoritative).
                    full = renderer.render(RenderRequest(
                        timeline=timeline, output_path=master_path,
                        renderer=backend, export_profiles=profiles))
                    exports = full.exports
        return master, exports, rsw.elapsed_s, esw.elapsed_s


def run_pipeline(
    config: PipelineConfig,
    *,
    script: str | None = None,
    script_path: Path | str | None = None,
    reference: Path | str | None = None,
    output_name: str = "reel",
) -> PipelineResult:
    """Convenience one-shot: build a :class:`CreatorPipeline` and run it."""
    return CreatorPipeline(config).run(
        script=script, script_path=script_path,
        reference=reference, output_name=output_name)
