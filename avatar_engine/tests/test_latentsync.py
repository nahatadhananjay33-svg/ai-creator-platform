"""Regression tests for Phase A4.7 — LatentSync integration (M1: installer +
weight manifest).

Covers the weight manifest + verification, the hardened install spec, and the
manifest-driven prefetch. Deterministic; no GPU, no network, no weights. Adapter
+ smoke-test tests land in later milestones.
"""
from __future__ import annotations

from pathlib import Path

from foundation.model_manager.installer import InstallationManager
from avatar_engine.models import latentsync_weights as lw
from avatar_engine.models.install_specs import INSTALL_SPECS


# --------------------------------------------------------------- install spec
def test_latentsync_install_spec_complete():
    spec = INSTALL_SPECS["latentsync"]
    assert spec.git_repo and "bytedance/LatentSync" in spec.git_repo
    assert spec.torch == "auto"                       # GPU-aware wheels (A3.8)
    assert spec.prefetch_code and "hf_hub_download" in spec.prefetch_code
    # A4.7: manifest-driven download, NOT the repo's huggingface-cli/conda setup.
    assert "setup_env.sh" not in spec.prefetch_code
    assert "huggingface-cli" not in spec.prefetch_code
    assert spec.supported_on_this_platform in (True, False)  # Linux-gated


def test_latentsync_torch_pinned_cu121():
    # LatentSync's requirements.txt pins torch 2.5.1 / cu121; the T4 (sm_75) runs
    # those wheels. An unpinned torch risks ABI/deps drift against diffusers 0.32.
    spec = INSTALL_SPECS["latentsync"]
    assert spec.torch_packages == ("torch==2.5.1", "torchvision==0.20.1")
    assert spec.torch_cuda_index == "https://download.pytorch.org/whl/cu121"
    args, label = InstallationManager.resolve_torch_install(spec, gpu_target=True)
    assert "torch==2.5.1" in args and "cu121" in label


def test_latentsync_pins_hub_030_and_setuptools():
    # huggingface_hub 0.30.2 is upstream's own pin (transformers 4.48/diffusers
    # 0.32 API); setuptools<81 because librosa 0.10.1 imports pkg_resources and
    # uv venvs ship no setuptools.
    spec = INSTALL_SPECS["latentsync"]
    pkgs = [p for group in spec.pip_groups for p in group]
    assert "huggingface_hub==0.30.2" in pkgs
    setuptools_pins = [p for p in pkgs if p.replace(" ", "").startswith("setuptools")]
    assert setuptools_pins == ["setuptools<81"], setuptools_pins
    # gradio is web-app only and deliberately omitted from the inference install.
    assert not any(p.startswith("gradio") for p in pkgs)


def test_verify_imports_only_covers_pip_group_packages():
    # verify_imports runs BEFORE clone + prefetch — must not list weights/repo pkgs.
    spec = INSTALL_SPECS["latentsync"]
    pip_group_pkgs = " ".join(p for group in spec.pip_groups for p in group)
    for name in spec.verify_imports:
        assert name in pip_group_pkgs or name == "cv2", name


# --------------------------------------------------------------- manifest
def test_manifest_matches_upstream_layout():
    rel = {w.relpath for w in lw.LATENTSYNC_WEIGHTS}
    assert rel == {"latentsync_unet.pt", "whisper/tiny.pt"}
    assert all(w.required for w in lw.LATENTSYNC_WEIGHTS)


def test_manifest_every_weight_has_hf_source_relpath_ends_with_filename():
    for w in lw.LATENTSYNC_WEIGHTS:
        assert w.repo_id == "ByteDance/LatentSync-1.6"
        assert w.hf_filename and w.relpath.endswith(w.hf_filename), w.relpath


def test_required_weight_paths_under_checkpoints(tmp_path):
    paths = lw.required_weight_paths(tmp_path)
    assert paths == [tmp_path / "checkpoints" / "latentsync_unet.pt",
                     tmp_path / "checkpoints" / "whisper" / "tiny.pt"]


# --------------------------------------------------------------- verification
def _write(root: Path, rel: str, nbytes: int) -> None:
    p = lw.weights_root(root) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * nbytes)


def test_weight_missing_when_absent(tmp_path):
    statuses = lw.check_weights(tmp_path)
    assert all(s.status == "missing" for s in statuses)
    assert lw.all_required_valid(statuses) is False


def test_weight_corrupted_when_truncated(tmp_path):
    _write(tmp_path, "latentsync_unet.pt", 10)   # < 100k floor
    s = lw.check_weight(tmp_path, next(w for w in lw.LATENTSYNC_WEIGHTS
                                       if w.relpath == "latentsync_unet.pt"))
    assert s.status == "corrupted"


def test_required_valid_true_when_all_present(tmp_path):
    for w in lw.LATENTSYNC_WEIGHTS:
        _write(tmp_path, w.relpath, 200_000)
    assert lw.all_required_valid(lw.check_weights(tmp_path)) is True


# --------------------------------------------------------------- prefetch
def test_prefetch_downloads_from_manifest_and_validates(tmp_path):
    code = lw.build_prefetch_code(tmp_path)
    assert "ensurepip" in code                     # uv venvs are pip-less
    assert "hf_hub_download" in code and "snapshot_download" in code
    for w in lw.LATENTSYNC_WEIGHTS:
        assert repr(w.relpath) in code
    assert "stabilityai/sd-vae-ft-mse" in code     # VAE pre-warm
    # Hard validation: a partial download must raise, never report false success.
    assert "required LatentSync weights missing after download" in code
    compile(code, "<prefetch>", "exec")            # must be valid Python
