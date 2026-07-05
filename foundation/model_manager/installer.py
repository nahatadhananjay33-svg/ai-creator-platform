"""Reusable, resumable model installation manager.

Design (extends Phase A1, no redesign):
- Each model installs into its own virtualenv under ``.venvs/`` (models have
  mutually incompatible dependency pins; isolation is the only sane policy —
  this codifies the rule documented in voice_engine/docs/INSTALLATION.md).
- ``uv`` is used when available (shared wheel cache -> resumable, fast,
  disk-cheap); falls back to stdlib venv + pip.
- All state persists in ``foundation.cache.DiskCache`` namespace
  ``model-installs``: re-running the installer skips completed steps and
  re-verifies imports, so interrupted downloads simply resume.
- The manager knows nothing about voice models specifically; engines supply
  :class:`InstallSpec` objects (see voice_engine/models/install_specs.py).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Sequence

from foundation.cache import DiskCache
from foundation.constants.paths import PROJECT_ROOT
from foundation.logging import get_logger
from foundation.model_manager.environment import EnvironmentReport, probe_torch
from foundation.shared_utils.timing import Stopwatch, utc_now_iso

logger = get_logger("foundation.model_manager.installer")

VENVS_DIR = PROJECT_ROOT / ".venvs"
REPOS_DIR = PROJECT_ROOT / ".venvs" / "_repos"

#: CPU wheel index for torch when CUDA is unusable.
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


def model_venv_python(model_id: str, venvs_dir: Path | None = None) -> Path:
    """Interpreter path for a model's isolated venv.

    Single source of truth for the per-model venv layout, shared by the
    installer *and* the adapters (which dispatch inference/diagnostics into
    that interpreter). Mirrors ``InstallationManager.venv_python``.
    """
    base = (venvs_dir or VENVS_DIR) / model_id
    if sys.platform == "win32":
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


@dataclass(frozen=True)
class InstallSpec:
    """Everything needed to install and verify one model environment."""

    model_id: str
    python_version: str = "3.12"
    #: pip requirement groups installed in order (each group = one pip call).
    pip_groups: tuple[tuple[str, ...], ...] = ()
    #: torch flavor: "cpu" | "cuda" | "none" (installed before pip_groups).
    torch: str = "cpu"
    #: import names that must succeed inside the venv to count as installed.
    verify_imports: tuple[str, ...] = ()
    #: optional python snippet run inside the venv to prefetch checkpoints.
    prefetch_code: str | None = None
    #: optional upstream repository to clone (repo-project models — most avatar
    #: stacks are run-from-clone, not pip packages). Cloned to repos_dir/<model_id>.
    git_repo: str | None = None
    #: optional branch/tag/commit to checkout after cloning.
    git_ref: str | None = None
    #: expected download size, for disk checks / reporting.
    approx_download_gb: float = 1.0
    #: platform gate: set False with a reason when known-broken here.
    supported_on_this_platform: bool = True
    platform_notes: str = ""
    env_vars: dict[str, str] = field(default_factory=dict)


@dataclass
class InstallResult:
    model_id: str
    status: str  # "installed" | "failed" | "skipped" | "already-installed"
    venv_python: str | None = None
    repo_dir: str | None = None
    duration_s: float = 0.0
    error: str | None = None
    verified_imports: list[str] = field(default_factory=list)
    torch_version: str | None = None
    log_tail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstallationManager:
    def __init__(self, venvs_dir: Path | None = None, repos_dir: Path | None = None,
                 timeout_s: int = 1800) -> None:
        self.venvs_dir = venvs_dir or VENVS_DIR
        self.repos_dir = repos_dir or REPOS_DIR
        self.timeout_s = timeout_s
        self.cache = DiskCache("model-installs")
        self._uv = shutil.which("uv")

    # ------------------------------------------------------------ repo clones
    def repo_dir(self, model_id: str) -> Path:
        return self.repos_dir / model_id

    def _ensure_repo(self, spec: InstallSpec) -> Path:
        """Clone (or reuse) the upstream repository. Resumable."""
        assert spec.git_repo is not None
        target = self.repo_dir(spec.model_id)
        if (target / ".git").exists():
            return target
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        proc = self._run(["git", "clone", "--depth", "1", spec.git_repo, str(target)])
        if proc.returncode != 0:
            raise RuntimeError(f"git clone failed: {proc.stderr[-600:]}")
        if spec.git_ref:
            proc = self._run(["git", "-C", str(target), "fetch", "--depth", "1",
                              "origin", spec.git_ref])
            proc = self._run(["git", "-C", str(target), "checkout", spec.git_ref])
            if proc.returncode != 0:
                raise RuntimeError(f"git checkout {spec.git_ref} failed: {proc.stderr[-400:]}")
        return target

    # ------------------------------------------------------------ primitives
    def venv_python(self, model_id: str) -> Path:
        return model_venv_python(model_id, self.venvs_dir)

    def _run(self, args: Sequence[str], env_vars: dict[str, str] | None = None,
             timeout_s: int | None = None) -> subprocess.CompletedProcess[str]:
        import os

        env = {**os.environ, **(env_vars or {})}
        logger.info("exec", extra={"context": {"cmd": " ".join(map(str, args[:6])) + (" ..." if len(args) > 6 else "")}})
        return subprocess.run(
            list(map(str, args)), capture_output=True, text=True,
            timeout=timeout_s or self.timeout_s, env=env, encoding="utf-8", errors="replace",
        )

    def _ensure_venv(self, spec: InstallSpec) -> Path:
        python = self.venv_python(spec.model_id)
        if python.exists():
            return python
        self.venvs_dir.mkdir(parents=True, exist_ok=True)
        if self._uv:
            # --clear: replace half-created venv directories from interrupted runs
            proc = self._run([self._uv, "venv", "--clear", str(self.venvs_dir / spec.model_id),
                              "--python", spec.python_version])
        else:
            proc = self._run([sys.executable, "-m", "venv", str(self.venvs_dir / spec.model_id)])
        if proc.returncode != 0:
            raise RuntimeError(f"venv creation failed: {proc.stderr[-800:]}")
        return python

    def _pip_install(self, python: Path, packages: Sequence[str],
                     env_vars: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if self._uv:
            cmd = [self._uv, "pip", "install", "--python", str(python), *packages]
        else:
            cmd = [str(python), "-m", "pip", "install", *packages]
        proc = self._run(cmd, env_vars=env_vars)
        if proc.returncode != 0:  # one retry — transient network failures are common
            logger.warning("pip install failed, retrying once",
                           extra={"context": {"packages": " ".join(packages)[:120]}})
            proc = self._run(cmd, env_vars=env_vars)
        return proc

    def _verify_imports(self, python: Path, imports: Sequence[str]) -> tuple[list[str], str | None]:
        ok: list[str] = []
        for name in imports:
            proc = self._run([python, "-c", f"import {name}"], timeout_s=300)
            if proc.returncode != 0:
                return ok, f"import {name} failed: {proc.stderr.strip()[-500:]}"
            ok.append(name)
        return ok, None

    # ------------------------------------------------------------ public API
    def status(self, model_id: str) -> dict[str, Any] | None:
        return self.cache.get(f"install:{model_id}")

    def install(self, spec: InstallSpec, env: EnvironmentReport, force: bool = False) -> InstallResult:
        """Install one model environment. Resumable and idempotent."""
        if not spec.supported_on_this_platform:
            result = InstallResult(spec.model_id, "skipped", error=spec.platform_notes)
            self.cache.put(f"install:{spec.model_id}", {**result.to_dict(), "at": utc_now_iso()})
            return result

        previous = self.status(spec.model_id)
        python = self.venv_python(spec.model_id)
        if not force and previous and previous.get("status") == "installed" and python.exists():
            verified, err = self._verify_imports(python, spec.verify_imports)
            if err is None:
                repo = str(self._ensure_repo(spec)) if spec.git_repo else None
                return InstallResult(spec.model_id, "already-installed",
                                     venv_python=str(python), verified_imports=verified,
                                     torch_version=previous.get("torch_version"),
                                     repo_dir=repo)
            logger.warning("Previous install no longer verifies; reinstalling",
                           extra={"context": {"model": spec.model_id, "error": err}})

        result = InstallResult(spec.model_id, "failed")
        with Stopwatch() as sw:
            try:
                python = self._ensure_venv(spec)
                result.venv_python = str(python)

                if spec.torch != "none":
                    torch_pkgs = ["torch", "torchaudio"]
                    args = torch_pkgs + (["--index-url", TORCH_CPU_INDEX]
                                         if spec.torch == "cpu" or not env.cuda_usable else [])
                    proc = self._pip_install(python, args, spec.env_vars)
                    if proc.returncode != 0:
                        raise RuntimeError(f"torch install failed: {proc.stderr[-800:]}")

                for group in spec.pip_groups:
                    proc = self._pip_install(python, group, spec.env_vars)
                    if proc.returncode != 0:
                        raise RuntimeError(
                            f"pip install {' '.join(group)[:120]} failed: {proc.stderr[-800:]}"
                        )
                    result.log_tail = (proc.stdout or "")[-400:]

                verified, err = self._verify_imports(python, spec.verify_imports)
                result.verified_imports = verified
                if err:
                    raise RuntimeError(err)

                if spec.git_repo:
                    result.repo_dir = str(self._ensure_repo(spec))

                if spec.prefetch_code:
                    proc = self._run([python, "-c", spec.prefetch_code], spec.env_vars,
                                     timeout_s=self.timeout_s)
                    if proc.returncode != 0:
                        raise RuntimeError(f"checkpoint prefetch failed: {proc.stderr[-800:]}")

                result.torch_version = probe_torch(str(python)).version
                result.status = "installed"
            except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                result.error = str(exc)[-1000:]
                logger.error("Install failed",
                             extra={"context": {"model": spec.model_id, "error": result.error[:200]}})
        result.duration_s = round(sw.elapsed_s, 1)
        self.cache.put(f"install:{spec.model_id}", {**result.to_dict(), "at": utc_now_iso()})
        return result
