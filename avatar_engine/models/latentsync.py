"""LatentSync adapter (real, Phase A4.7).

Video-driven lip-sync: re-syncs a **template video**'s mouth to driving audio
(`driving_video` + `driving_audio` -> `GenerationResult`) — LatentSync is an
end-to-end audio-conditioned latent-diffusion editor (the accuracy counterpart
to MuseTalk's real-time inpainting). It is a run-from-clone project: the adapter
runs the repo's `scripts.inference` in LatentSync's own venv with a sanitized
env, then returns the produced mp4.

Weights are prefetched by the installer (see latentsync_weights.py). LatentSync
needs a CUDA GPU; on the T4 (compute 7.5) it runs fp32 (upstream gates fp16 on
cc > 7), so the default UNet config is 256² (see `_UNET_CONFIG_DEFAULT`) — 512²
fp32 overflows the T4's 16 GB.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from foundation.exceptions import ModelError
from foundation.model_manager.installer import REPOS_DIR

from avatar_engine.models.base import BaseAvatarAdapter
from avatar_engine.models.diagnostics import sanitized_subprocess_env
from avatar_engine.models.interface import GenerationRequest, GenerationResult
from avatar_engine.models.latentsync_weights import check_weights, required_weight_paths
from avatar_engine.models.media import probe_video
from avatar_engine.research.catalog import get_profile

#: UNet config (relative to the repo). Upstream's stage2_512 (512²) overflows a
#: T4's 16 GB in fp32 — and LatentSync forces fp32 on Turing: inference.py gates
#: fp16 on ``get_device_capability()[0] > 7``, which is False for the T4 (cc 7.5).
#: So the default is upstream's 256² ``stage2_efficient`` config (same 1.6 UNet:
#: cross_attention_dim 384, sample_size 64), whose ¼-size activations fit the T4.
#: Override via ``config["unet_config"]`` to run 512 on a larger, fp16-capable GPU.
_UNET_CONFIG_DEFAULT = "configs/unet/stage2_efficient.yaml"
_UNET_CKPT = "checkpoints/latentsync_unet.pt"


class LatentSyncAdapter(BaseAvatarAdapter):
    SPEC = get_profile("latentsync").spec
    # Video-driven lip-sync: a template video + audio (unlike MuseTalk's portrait).
    REQUIRED_INPUTS = ("driving_video", "driving_audio")
    IMPORT_PACKAGES = ("diffusers", "cv2")
    PIP_PACKAGES = ("see avatar_engine/models/install_specs.py [latentsync]",)

    DEFAULT_TIMEOUT_S = 3600

    @property
    def repo_dir(self) -> Path:
        return Path(self.config.get("repo_dir", REPOS_DIR / "latentsync"))

    @property
    def unet_config(self) -> str:
        """UNet config path (relative to repo_dir); see ``_UNET_CONFIG_DEFAULT``."""
        return self.config.get("unet_config", _UNET_CONFIG_DEFAULT)

    def required_paths(self) -> list[Path]:
        # Repo inference entrypoint + UNet config + every inference weight, so a
        # missing checkpoint is named precisely rather than a bare directory.
        return [self.repo_dir / "scripts" / "inference.py",
                self.repo_dir / self.unet_config,
                *required_weight_paths(self.repo_dir)]

    def weight_report(self) -> list[dict]:
        """Per-weight status (validated / missing / corrupted)."""
        return [s.to_dict() for s in check_weights(self.repo_dir)]

    def inference_command(self, video_path: Path, audio_path: Path,
                          out_path: Path) -> list[str]:
        """The upstream stage2 inference command (from inference.sh), pointed at
        ``self.unet_config`` (256² ``stage2_efficient`` by default — see it)."""
        return [
            str(self.venv_python), "-m", "scripts.inference",
            "--unet_config_path", self.unet_config,
            "--inference_ckpt_path", _UNET_CKPT,
            "--inference_steps", str(int(self.config.get("inference_steps", 20))),
            "--guidance_scale", str(float(self.config.get("guidance_scale", 1.5))),
            "--enable_deepcache",
            "--video_path", str(video_path),
            "--audio_path", str(audio_path),
            "--video_out_path", str(out_path),
        ]

    def _load_impl(self) -> None:
        if not (self.repo_dir / "scripts" / "inference.py").exists():
            raise ModelError(
                f"LatentSync repo not found at {self.repo_dir}; run the installer",
                engine=self.engine_id,
            )
        self._model = {"repo": self.repo_dir}

    def _generate_impl(self, request: GenerationRequest, output_path: Path) -> GenerationResult:
        video = Path(request.driving_video).resolve()
        audio = Path(request.driving_audio).resolve()
        cmd = self.inference_command(video, audio, output_path.resolve())
        # Dispatch into LatentSync's venv (cwd=repo so `scripts.inference`,
        # `configs/`, and relative checkpoint paths resolve) with a sanitized env.
        proc = subprocess.run(
            cmd, cwd=self.repo_dir, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            env=sanitized_subprocess_env(self.venv_dir),
            timeout=int(self.config.get("timeout_s", self.DEFAULT_TIMEOUT_S)),
        )
        if proc.returncode != 0:
            raise ModelError(
                f"LatentSync inference failed: {(proc.stderr or proc.stdout)[-800:]}",
                engine=self.engine_id,
            )
        if not output_path.exists():
            raise ModelError(
                f"LatentSync completed but wrote no video at {output_path}",
                engine=self.engine_id,
            )
        probe = probe_video(output_path)
        if not probe.readable:
            raise ModelError(f"LatentSync output not decodable: {output_path}",
                             engine=self.engine_id)
        return GenerationResult(
            video_path=output_path, engine_id=self.engine_id, generation_time_s=0.0,
            duration_s=probe.duration_s, fps=probe.fps, width=probe.width,
            height=probe.height,
            metadata={
                "mode": Path(self.unet_config).stem,
                "frames": probe.frame_count,
                "device_requested": self.device.value,
                "device_actual": self.actual_device,
            },
        )
