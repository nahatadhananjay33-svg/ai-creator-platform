"""LivePortrait adapter (real, Phase A3.5).

Video-driven reenactment: animates a source portrait with a driving VIDEO
(not audio) — REQUIRED_INPUTS differs from audio-driven models. Runs the
cloned repo's ``inference.py`` in a subprocess; ``--flag_force_cpu`` is an
upstream-supported path on hosts without CUDA.

License note (research doc): InsightFace detection models are research-only
— the adapter exists for benchmarking; production use requires replacing
the detection stack.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from foundation.exceptions import ModelError
from foundation.model_manager.installer import REPOS_DIR

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.diagnostics import sanitized_subprocess_env
from avatar_engine.models.interface import GenerationRequest, GenerationResult
from avatar_engine.models.liveportrait_weights import check_weights, required_weight_paths
from avatar_engine.models.media import probe_video
from avatar_engine.research.catalog import get_profile


class LivePortraitAdapter(BaseAvatarAdapter):
    SPEC = get_profile("liveportrait").spec
    REQUIRED_INPUTS = ("source_image", "driving_video")
    IMPORT_PACKAGES = ("insightface", "cv2")
    PIP_PACKAGES = ("see avatar_engine/models/install_specs.py [liveportrait]",)

    DEFAULT_TIMEOUT_S = 3600

    @property
    def repo_dir(self) -> Path:
        return Path(self.config.get("repo_dir", REPOS_DIR / "liveportrait"))

    def required_paths(self) -> list[Path]:
        # Repo entrypoint + EVERY required pretrained weight (from the upstream
        # manifest) — so availability fails precisely when a weight is missing,
        # not just when the top-level directory is absent.
        return [self.repo_dir / "inference.py", *required_weight_paths(self.repo_dir)]

    def weight_report(self) -> list[dict]:
        """Per-weight status (validated/missing/corrupted/checksum_mismatch)."""
        return [s.to_dict() for s in check_weights(self.repo_dir)]

    def _load_impl(self) -> None:
        if not (self.repo_dir / "inference.py").exists():
            raise ModelError(
                f"LivePortrait repo not found at {self.repo_dir}; run the installer",
                engine=self.engine_id,
            )
        self._model = {"repo": self.repo_dir}

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        work_dir = output_path.parent / f"{output_path.stem}-work"
        work_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            str(self.venv_python), "inference.py",
            "-s", str(Path(request.source_image).resolve()),
            "-d", str(Path(request.driving_video).resolve()),
            "--output-dir", str(work_dir.resolve()),
        ]
        if self.device.value == "cpu":
            cmd.append("--flag_force_cpu")
        proc = subprocess.run(
            cmd, cwd=self.repo_dir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=sanitized_subprocess_env(self.venv_dir),
            timeout=int(self.config.get("timeout_s", self.DEFAULT_TIMEOUT_S)),
        )
        if proc.returncode != 0:
            raise ModelError(
                f"LivePortrait inference failed: {(proc.stderr or proc.stdout)[-800:]}",
                engine=self.engine_id,
            )
        # upstream writes <src>--<drv>.mp4 (+ a *_concat.mp4 comparison strip)
        produced = [
            p for p in sorted(work_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
            if "concat" not in p.name
        ]
        if not produced:
            raise ModelError(
                f"LivePortrait completed but wrote no mp4 under {work_dir}",
                engine=self.engine_id,
            )
        import shutil

        shutil.move(str(produced[-1]), output_path)
        shutil.rmtree(work_dir, ignore_errors=True)

        probe = probe_video(output_path)
        if not probe.readable:
            raise ModelError(f"LivePortrait output not decodable: {output_path}",
                             engine=self.engine_id)
        return GenerationResult(
            video_path=output_path, engine_id=self.engine_id, generation_time_s=0.0,
            duration_s=probe.duration_s, fps=probe.fps, width=probe.width,
            height=probe.height,
            metadata={
                "frames": probe.frame_count,
                "device_requested": self.device.value,
                "device_actual": self.actual_device,
            },
        )
