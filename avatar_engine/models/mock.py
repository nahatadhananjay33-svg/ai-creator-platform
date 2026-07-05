"""Mock avatar adapter: exercises the full pipeline with no ML dependencies.

Generates a deterministic moving test-pattern AVI whose duration matches the
driving audio, so benchmark orchestration, evaluation, and reporting can be
tested end-to-end on any machine (same role as the voice engine's mock TTS
adapter).
"""
from __future__ import annotations

from pathlib import Path

from foundation.model_manager import HardwareRequirements, LicenseInfo, ModelSpec
from foundation.shared_utils import read_wav
from foundation.shared_utils.video_io import VideoFrames, write_raw_avi

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.interface import GenerationRequest, GenerationResult

_MOCK_SPEC = ModelSpec(
    model_id="mock",
    display_name="Mock Avatar",
    family="avatar",
    version="1.0",
    repo_url="",
    weights_source="",
    license=LicenseInfo("MIT", "MIT", True, "test double"),
    hardware=HardwareRequirements(None, None, 0.1, True, 0.0),
    tags=("mock", "testing"),
)


class MockAvatarAdapter(BaseAvatarAdapter):
    """Writes a synthetic talking-head-shaped video for pipeline testing."""

    SPEC = _MOCK_SPEC
    REQUIRED_INPUTS = ("source_image", "driving_audio")
    IMPORT_PACKAGES: tuple[str, ...] = ()
    PIP_PACKAGES: tuple[str, ...] = ()
    #: Pure-Python test double — runs in the current interpreter, no venv.
    RUNS_IN_VENV = False

    #: Small fixed raster keeps tests fast; enough pixels for frame metrics.
    WIDTH = 64
    HEIGHT = 64
    FPS = 25.0

    def _load_impl(self) -> None:
        self._model = object()  # nothing to load

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        assert request.driving_audio is not None  # enforced by REQUIRED_INPUTS
        audio = read_wav(request.driving_audio)
        n_frames = max(2, int(round(audio.duration_s * self.FPS)))

        frames: list[bytes] = []
        for t in range(n_frames):
            # A moving gradient plus a "mouth" bar that oscillates with time —
            # gives temporal-consistency and motion metrics something real.
            mouth_open = (t % 10) < 5
            frame = bytearray()
            for y in range(self.HEIGHT):
                for x in range(self.WIDTH):
                    in_mouth = 40 <= y < 48 and 24 <= x < 40 and mouth_open
                    if in_mouth:
                        frame += b"\x20\x20\x80"
                    else:
                        frame += bytes(((x * 3 + t) % 256, (y * 3) % 256, 128))
            frames.append(bytes(frame))

        avi_path = output_path.with_suffix(".avi")
        write_raw_avi(avi_path, VideoFrames(frames, self.WIDTH, self.HEIGHT, self.FPS))
        return GenerationResult(
            video_path=avi_path,
            engine_id=self.engine_id,
            generation_time_s=0.0,  # overwritten by the base class
            duration_s=n_frames / self.FPS,
            fps=self.FPS,
            width=self.WIDTH,
            height=self.HEIGHT,
            metadata={"synthetic": True, "device_actual": self.actual_device},
        )
