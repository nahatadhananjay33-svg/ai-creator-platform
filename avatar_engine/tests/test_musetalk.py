"""Regression tests for Phase A4.0 — MuseTalk integration.

Covers the weight manifest + verification, the install spec, the real adapter
(availability, inference command, config yaml), registry wiring, comparison
inclusion, and the notebook step. Deterministic; no GPU, no network, no weights.
"""
from __future__ import annotations

import sys

from foundation.benchmarking.results import CaseResult, CaseStatus, Measurement, RunResult
from foundation.model_manager.installer import InstallationManager
from avatar_engine.models import ADAPTER_CLASSES, create_adapter
from avatar_engine.models import musetalk_weights as mw
from avatar_engine.models.musetalk import MuseTalkAdapter
from avatar_engine.models.install_specs import INSTALL_SPECS
from avatar_engine.reporting.comparison import build_comparison


# --------------------------------------------------------------- registry / spec
def test_musetalk_is_real_adapter_not_planned():
    a = create_adapter("musetalk")
    assert isinstance(a, MuseTalkAdapter)
    assert ADAPTER_CLASSES["musetalk"] is MuseTalkAdapter
    assert a.RUNS_IN_VENV is True
    assert a.REQUIRED_INPUTS == ("source_image", "driving_audio")  # audio-driven like SadTalker


def test_musetalk_install_spec_complete():
    spec = INSTALL_SPECS["musetalk"]
    assert spec.git_repo and "TMElyralab/MuseTalk" in spec.git_repo
    assert spec.torch == "auto"                       # GPU-aware wheels (A3.8)
    assert spec.prefetch_code and "download_weights.sh" in spec.prefetch_code
    assert "mim" in spec.prefetch_code                # MMLab stack
    assert spec.supported_on_this_platform in (True, False)  # Linux-gated


def test_verify_imports_only_covers_pip_group_packages():
    # Regression (A4.0 fix): verify_imports runs BEFORE git clone + prefetch, so
    # it must NOT list packages installed by the prefetch (mmpose/mmcv via mim) —
    # otherwise the install aborts before cloning the repo / downloading weights.
    spec = INSTALL_SPECS["musetalk"]
    assert "mmpose" not in spec.verify_imports
    assert "mmcv" not in spec.verify_imports
    pip_group_pkgs = " ".join(pkg for group in spec.pip_groups for pkg in group)
    for name in spec.verify_imports:
        # diffusers/cv2 come from the pip_groups (cv2 via opencv-python).
        assert name in pip_group_pkgs or name == "cv2", name
    # mmpose is still verified at RUNTIME by the adapter's diagnostics.
    assert "mmpose" in MuseTalkAdapter.IMPORT_PACKAGES


def test_musetalk_torch_pinned_to_match_mmcv():
    # Regression (A4.0 prefetch fix): the prefetch runs `mim install mmcv==2.0.1`,
    # which only has prebuilt wheels for torch 2.0.x + cu118 (MuseTalk's documented
    # environment). An unpinned/latest torch -> no matching mmcv wheel -> mim source
    # build -> the prefetch fails ("checkpoint prefetch failed"). Torch MUST be
    # pinned to 2.0.1 / cu118, exactly like SadTalker.
    spec = INSTALL_SPECS["musetalk"]
    assert spec.torch_packages == ("torch==2.0.1", "torchvision==0.15.2", "torchaudio==2.0.2")
    assert spec.torch_cuda_index == "https://download.pytorch.org/whl/cu118"
    assert "mmcv==2.0.1" in spec.prefetch_code  # the pin that requires this torch
    # On a GPU host the installer must emit the matching cu118 wheels.
    args, label = InstallationManager.resolve_torch_install(spec, gpu_target=True)
    assert "torch==2.0.1" in args and "cu118" in label
    # ...and never the latest/unpinned torch that breaks the mmcv wheel match.
    assert "torch" not in args or "torch==2.0.1" in args


def test_musetalk_declares_setuptools_for_pkg_resources():
    # Regression (A4.3 fix): uv-created venvs ship no setuptools, so `pkg_resources`
    # is absent. openmim/`mim install` and the MMLab stack (mmengine/mmcv/mmdet/mmpose)
    # import pkg_resources at build+import time, and the adapter imports mmpose at
    # runtime -> "ModuleNotFoundError: pkg_resources" unless setuptools is installed.
    # The spec must declare setuptools in its pip_groups (traditional venv bundled it;
    # uv does not).
    spec = INSTALL_SPECS["musetalk"]
    pkgs = [pkg for group in spec.pip_groups for pkg in group]
    setuptools_pins = [p for p in pkgs if p.replace(" ", "").startswith("setuptools")]
    assert setuptools_pins, "musetalk must install setuptools (uv venvs lack pkg_resources)"
    # Pinned below 81, where setuptools deprecates/removes pkg_resources, keeping the
    # MMLab-era (mmcv 2.0.1) stack importable.
    assert setuptools_pins == ["setuptools<70"], setuptools_pins


def test_prefetch_puts_venv_bin_on_path():
    # download_weights.sh calls huggingface-cli/gdown from the venv bin, which is
    # not on PATH in an unactivated uv venv — the prefetch must add it.
    code = INSTALL_SPECS["musetalk"].prefetch_code
    assert "bindir" in code and "PATH" in code and "env=env" in code


# --------------------------------------------------------------- weights
def test_manifest_matches_upstream_layout():
    rel = {w.relpath for w in mw.MUSETALK_WEIGHTS}
    for expected in (
        "musetalkV15/unet.pth", "musetalkV15/musetalk.json",
        "sd-vae/diffusion_pytorch_model.bin", "whisper/pytorch_model.bin",
        "dwpose/dw-ll_ucoco_384.pth", "face-parse-bisent/79999_iter.pth",
        "face-parse-bisent/resnet18-5c106cde.pth",
    ):
        assert expected in rel, expected
    assert any(w.required_for_v15 for w in mw.MUSETALK_WEIGHTS)


def _write(repo, relpath, size):
    p = mw.weights_root(repo) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * size)
    return p


def test_all_missing(tmp_path):
    st = mw.check_weights(tmp_path)
    assert all(s.status == "missing" for s in st)
    assert mw.all_required_valid(st) is False


def test_valid_and_corrupted(tmp_path):
    _write(tmp_path, "musetalkV15/unet.pth", 200_000)        # ok
    _write(tmp_path, "dwpose/dw-ll_ucoco_384.pth", 500)      # truncated weight
    by = {s.relpath: s for s in mw.check_weights(tmp_path)}
    assert by["musetalkV15/unet.pth"].status == "validated"
    assert by["dwpose/dw-ll_ucoco_384.pth"].status == "corrupted"


def test_config_json_validated_when_present(tmp_path):
    _write(tmp_path, "musetalkV15/musetalk.json", 200)       # small config is fine
    assert mw.check_weight(
        tmp_path, next(w for w in mw.MUSETALK_WEIGHTS if w.relpath.endswith("musetalk.json"))
    ).status == "validated"


def test_required_valid_true_when_all_required_present(tmp_path):
    for w in mw.MUSETALK_WEIGHTS:
        if w.required_for_v15:
            _write(tmp_path, w.relpath, 200_000 if w.relpath.endswith(mw._WEIGHT_EXTS) else 500)
    assert mw.all_required_valid(mw.check_weights(tmp_path)) is True


def test_prefetch_installs_mmlab_and_downloads(tmp_path):
    code = mw.build_prefetch_code(tmp_path)
    assert "ensurepip" in code                    # uv venvs are pip-less
    assert "openmim" in code and "mim" in code
    for v in ("mmcv==2.0.1", "mmdet==3.1.0", "mmpose==1.1.0"):
        assert v in code
    assert "download_weights.sh" in code


# --------------------------------------------------------------- adapter
def _fake_repo(tmp_path, weights=True):
    repo = tmp_path / "musetalk"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "inference.py").write_text("# fake")
    if weights:
        for w in mw.MUSETALK_WEIGHTS:
            if w.required_for_v15:
                _write(repo, w.relpath, 200_000 if w.relpath.endswith(mw._WEIGHT_EXTS) else 500)
    return repo


def test_required_paths_include_weights_and_entrypoint(tmp_path):
    repo = _fake_repo(tmp_path)
    a = MuseTalkAdapter(config={"repo_dir": repo})
    req = {str(p) for p in a.required_paths()}
    assert str(repo / "scripts" / "inference.py") in req
    assert str(mw.weights_root(repo) / "musetalkV15" / "unet.pth") in req


def test_adapter_names_missing_weight(tmp_path):
    repo = _fake_repo(tmp_path, weights=False)
    a = MuseTalkAdapter(config={"repo_dir": repo, "venv_python": sys.executable})
    diag = a.diagnostics()
    assert diag.available is False
    assert "missing files" in diag.reason
    assert any("unet.pth" in ps["path"] for ps in diag.required_paths if not ps["exists"])


def test_inference_command_is_upstream_v15(tmp_path):
    a = MuseTalkAdapter(config={"repo_dir": tmp_path})
    cmd = a.inference_command(tmp_path / "cfg.yaml", tmp_path / "res")
    assert cmd[1:3] == ["-m", "scripts.inference"]
    assert "--version" in cmd and cmd[cmd.index("--version") + 1] == "v15"
    assert "models/musetalkV15/unet.pth" in cmd


def test_inference_config_yaml_written(tmp_path):
    from avatar_engine.models.interface import GenerationRequest
    img = tmp_path / "p.png"; img.write_bytes(b"x")
    aud = tmp_path / "a.wav"; aud.write_bytes(b"x")
    a = MuseTalkAdapter(config={"repo_dir": tmp_path, "bbox_shift": -7})
    work = tmp_path / "work"; work.mkdir()
    cfg = a._write_inference_config(
        GenerationRequest(source_image=img, driving_audio=aud), work)
    text = cfg.read_text()
    assert "video_path:" in text and "audio_path:" in text and "bbox_shift: -7" in text


def test_adapter_weight_report(tmp_path):
    repo = _fake_repo(tmp_path)
    rep = MuseTalkAdapter(config={"repo_dir": repo}).weight_report()
    assert len(rep) == len(mw.MUSETALK_WEIGHTS)


# --------------------------------------------------------------- comparison
def _run(model):
    run = RunResult(run_id="r", title="t")
    c = CaseResult(case_id=f"{model}-s", subject_id=model, scenario="neutral_speech",
                   status=CaseStatus.PASSED)
    c.add(Measurement("generation_time_s", 5.0, "s"))
    c.add(Measurement("device", "cuda"))
    run.cases.append(c)
    return run


def test_comparison_includes_musetalk():
    summaries = build_comparison([_run("sadtalker"), _run("musetalk")])
    assert {s.model_id for s in summaries} == {"sadtalker", "musetalk"}
