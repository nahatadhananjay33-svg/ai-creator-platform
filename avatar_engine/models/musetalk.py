"""MuseTalk adapter (real, Phase A4.0).

Audio-driven lip-sync: animates a source portrait's mouth to driving audio —
same task shape as SadTalker (``source_image`` + ``driving_audio`` ->
``GenerationResult``). MuseTalk is a run-from-clone project whose inference is
**config-yaml-driven**: it reads a YAML mapping tasks to ``video_path`` (an
image or video) + ``audio_path``. The adapter therefore writes a temporary
inference config, then runs the repo's ``scripts.inference`` (v1.5) in the
model's own venv, exactly like SadTalker/LivePortrait dispatch to their venvs.

Weights are prefetched by the installer (see musetalk_weights.py). MuseTalk
needs the MMLab stack (mmcv/mmpose) which compiles only on Linux/CUDA — the
install spec gates this off native Windows.
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
from avatar_engine.models.musetalk_weights import check_weights, required_weight_paths
from avatar_engine.research.catalog import get_profile


class MuseTalkAdapter(BaseAvatarAdapter):
    SPEC = get_profile("musetalk").spec
    REQUIRED_INPUTS = ("source_image", "driving_audio")
    IMPORT_PACKAGES = ("diffusers", "mmpose", "cv2")
    PIP_PACKAGES = ("see avatar_engine/models/install_specs.py [musetalk]",)

    DEFAULT_TIMEOUT_S = 3600

    @property
    def repo_dir(self) -> Path:
        return Path(self.config.get("repo_dir", REPOS_DIR / "musetalk"))

    def required_paths(self) -> list[Path]:
        # Repo inference entrypoint + every v1.5 weight (from the manifest), so
        # a missing checkpoint is named precisely rather than a bare directory.
        return [self.repo_dir / "scripts" / "inference.py",
                *required_weight_paths(self.repo_dir)]

    def weight_report(self) -> list[dict]:
        """Per-weight status (validated / missing / corrupted)."""
        return [s.to_dict() for s in check_weights(self.repo_dir)]

    def inference_command(self, config_path: Path, result_dir: Path) -> list[str]:
        """The exact upstream v1.5 normal-inference command (documented)."""
        cmd = [
            str(self.venv_python), "-m", "scripts.inference",
            "--inference_config", str(config_path),
            "--result_dir", str(result_dir),
            "--unet_model_path", "models/musetalkV15/unet.pth",
            "--unet_config", "models/musetalkV15/musetalk.json",
            "--version", "v15",
        ]
        ffmpeg_path = self.config.get("ffmpeg_path")
        if ffmpeg_path:
            cmd += ["--ffmpeg_path", str(ffmpeg_path)]
        return cmd

    def _load_impl(self) -> None:
        if not (self.repo_dir / "scripts" / "inference.py").exists():
            raise ModelError(
                f"MuseTalk repo not found at {self.repo_dir}; run the installer",
                engine=self.engine_id,
            )
        self._model = {"repo": self.repo_dir}

    def _write_inference_config(self, request: GenerationRequest, work_dir: Path) -> Path:
        """Write MuseTalk's task YAML pointing at the portrait + driving audio."""
        image = Path(request.source_image).resolve().as_posix()
        audio = Path(request.driving_audio).resolve().as_posix()
        lines = [
            "benchmark:",
            f'  video_path: "{image}"',   # an image is accepted as a static frame
            f'  audio_path: "{audio}"',
        ]
        bbox_shift = self.config.get("bbox_shift")
        if bbox_shift is not None:
            lines.append(f"  bbox_shift: {int(bbox_shift)}")
        config_path = work_dir / "inference.yaml"
        config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return config_path

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        work_dir = output_path.parent / f"{output_path.stem}-work"
        work_dir.mkdir(parents=True, exist_ok=True)
        config_path = self._write_inference_config(request, work_dir)
        result_dir = work_dir / "results"

        cmd = self.inference_command(config_path, result_dir)
        # Dispatch into MuseTalk's own venv (cwd=repo so relative model paths and
        # `scripts.inference` resolve) with a sanitized environment.
        proc = subprocess.run(
            cmd, cwd=self.repo_dir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=sanitized_subprocess_env(self.venv_dir),
            timeout=int(self.config.get("timeout_s", self.DEFAULT_TIMEOUT_S)),
        )
        if proc.returncode != 0:
            raise ModelError(
                f"MuseTalk inference failed: {(proc.stderr or proc.stdout)[-800:]}",
                engine=self.engine_id,
            )
        produced = sorted(result_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not produced:
            raise ModelError(
                f"MuseTalk completed but wrote no mp4 under {result_dir}",
                engine=self.engine_id,
            )
        shutil.move(str(produced[-1]), output_path)
        shutil.rmtree(work_dir, ignore_errors=True)

        probe = probe_video(output_path)
        if not probe.readable:
            raise ModelError(f"MuseTalk output not decodable: {output_path}",
                             engine=self.engine_id)
        return GenerationResult(
            video_path=output_path, engine_id=self.engine_id, generation_time_s=0.0,
            duration_s=probe.duration_s, fps=probe.fps, width=probe.width,
            height=probe.height,
            metadata={
                "mode": "v15",
                "frames": probe.frame_count,
                "device_requested": self.device.value,
                "device_actual": self.actual_device,
            },
        )
