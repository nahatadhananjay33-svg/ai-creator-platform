"""SadTalker adapter (real, Phase A3.5).

SadTalker is a run-from-clone project (no package API), so the adapter
drives the cloned repo's ``inference.py`` in a subprocess using the current
interpreter — benchmark runs execute inside the sadtalker venv, exactly
like the voice engine's per-model venv pattern.

Verified configuration on this host (CPU-only): 256 mode, ``--preprocess
crop``, no enhancer, ``--cpu``. Checkpoints are prefetched by the installer
(see install_specs.py).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from foundation.exceptions import ModelError
from foundation.model_manager.installer import REPOS_DIR

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.diagnostics import sanitized_subprocess_env
from avatar_engine.models.interface import GenerationRequest, GenerationResult
from avatar_engine.models.media import probe_video
from avatar_engine.research.catalog import get_profile


class SadTalkerAdapter(BaseAvatarAdapter):
    SPEC = get_profile("sadtalker").spec
    REQUIRED_INPUTS = ("source_image", "driving_audio")
    IMPORT_PACKAGES = ("face_alignment", "basicsr", "cv2")
    PIP_PACKAGES = ("see avatar_engine/models/install_specs.py [sadtalker]",)

    #: generation timeout — CPU renders are minutes-per-second of video.
    DEFAULT_TIMEOUT_S = 3600

    @property
    def repo_dir(self) -> Path:
        return Path(self.config.get("repo_dir", REPOS_DIR / "sadtalker"))

    def required_paths(self) -> list[Path]:
        # Cloned repo entrypoint + the minimal 256-mode checkpoint (prefetched
        # by the installer). Availability is False with a precise reason if any
        # of these is missing.
        return [
            self.repo_dir / "inference.py",
            self.repo_dir / "checkpoints" / "SadTalker_V0.0.2_256.safetensors",
        ]

    def _load_impl(self) -> None:
        # Subprocess model: nothing resident; load = verify repo + checkpoints.
        if not (self.repo_dir / "inference.py").exists():
            raise ModelError(
                f"SadTalker repo not found at {self.repo_dir}; run the installer",
                engine=self.engine_id,
            )
        self._model = {"repo": self.repo_dir}

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        work_dir = output_path.parent / f"{output_path.stem}-work"
        work_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.venv_python), "inference.py",
            "--driven_audio", str(Path(request.driving_audio).resolve()),
            "--source_image", str(Path(request.source_image).resolve()),
            "--result_dir", str(work_dir.resolve()),
            "--preprocess", self.config.get("preprocess", "crop"),
            "--size", str(self.config.get("size", 256)),
        ]
        if self.config.get("still", True):
            cmd.append("--still")
        if self.device.value == "cpu":
            cmd.append("--cpu")
        # Dispatch into SadTalker's own venv with a sanitized environment so the
        # launcher's PYTHONPATH/VIRTUAL_ENV can't shadow the venv's packages.
        proc = subprocess.run(
            cmd, cwd=self.repo_dir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=sanitized_subprocess_env(self.venv_dir),
            timeout=int(self.config.get("timeout_s", self.DEFAULT_TIMEOUT_S)),
        )
        if proc.returncode != 0:
            raise ModelError(
                f"SadTalker inference failed: {(proc.stderr or proc.stdout)[-800:]}",
                engine=self.engine_id,
            )
        produced = sorted(work_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not produced:
            raise ModelError(
                f"SadTalker completed but wrote no mp4 under {work_dir}",
                engine=self.engine_id,
            )
        shutil.move(str(produced[-1]), output_path)
        shutil.rmtree(work_dir, ignore_errors=True)

        probe = probe_video(output_path)
        if not probe.readable:
            raise ModelError(f"SadTalker output not decodable: {output_path}",
                             engine=self.engine_id)
        return GenerationResult(
            video_path=output_path, engine_id=self.engine_id, generation_time_s=0.0,
            duration_s=probe.duration_s, fps=probe.fps, width=probe.width,
            height=probe.height,
            metadata={
                "mode": "256-crop",
                "frames": probe.frame_count,
                "device_requested": self.device.value,
                "device_actual": self.actual_device,
            },
        )
