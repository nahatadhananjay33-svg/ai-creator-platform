"""Regression tests for Phase A3.9 — LivePortrait completion.

Covers the weight manifest + verification (missing / corrupted / checksum /
resume-skip), adapter availability against the real required weights, the
driving-video plumbing that lets the video-driven model run in the existing
benchmark, and the SadTalker-vs-LivePortrait comparison report. Deterministic;
no GPU, no network, no real weights.
"""
from __future__ import annotations

import sys

from foundation.benchmarking.results import CaseResult, CaseStatus, Measurement, RunResult
from avatar_engine.benchmark import AvatarBenchmark, AvatarBenchmarkConfig
from avatar_engine.models import create_adapter
from avatar_engine.models import liveportrait_weights as lw
from avatar_engine.models.liveportrait import LivePortraitAdapter
from avatar_engine.reporting.comparison import build_comparison


# --------------------------------------------------------------- manifest
def test_manifest_has_all_upstream_weights():
    rel = {w.relpath for w in lw.LIVEPORTRAIT_WEIGHTS}
    assert lw.HF_REPO_ID == "KlingTeam/LivePortrait"
    assert len(lw.LIVEPORTRAIT_WEIGHTS) == 8
    for expected in (
        "liveportrait/base_models/appearance_feature_extractor.pth",
        "liveportrait/base_models/motion_extractor.pth",
        "liveportrait/base_models/spade_generator.pth",
        "liveportrait/base_models/warping_module.pth",
        "liveportrait/landmark.onnx",
        "liveportrait/retargeting_models/stitching_retargeting_module.pth",
        "insightface/models/buffalo_l/2d106det.onnx",
        "insightface/models/buffalo_l/det_10g.onnx",
    ):
        assert expected in rel, expected


def _write_weight(repo_dir, w, size_bytes):
    p = lw.pretrained_root(repo_dir) / w.relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\0" * size_bytes)
    return p


# --------------------------------------------------------------- verification
def test_all_missing_reported(tmp_path):
    statuses = lw.check_weights(tmp_path)
    assert all(s.status == "missing" for s in statuses)
    assert not lw.all_valid(statuses)
    assert len(lw.weights_to_download(tmp_path)) == 8


def test_valid_weight_validated(tmp_path):
    w = lw.LIVEPORTRAIT_WEIGHTS[0]
    _write_weight(tmp_path, w, w.expected_bytes)
    assert lw.check_weight(tmp_path, w).status == "validated"


def test_truncated_weight_corrupted(tmp_path):
    w = lw.LIVEPORTRAIT_WEIGHTS[2]  # 222 MB nominal
    _write_weight(tmp_path, w, 4096)  # truncated
    s = lw.check_weight(tmp_path, w)
    assert s.status == "corrupted" and "truncated" in s.reason.lower()


def test_checksum_mismatch_detected(tmp_path):
    from dataclasses import replace
    w = replace(lw.LIVEPORTRAIT_WEIGHTS[5], sha256="0" * 64)  # bogus expected hash
    _write_weight(tmp_path, w, w.expected_bytes)
    assert lw.check_weight(tmp_path, w).status == "checksum_mismatch"


def test_valid_files_not_redownloaded(tmp_path):
    w = lw.LIVEPORTRAIT_WEIGHTS[0]
    _write_weight(tmp_path, w, w.expected_bytes)          # one valid
    todo = {x.relpath for x in lw.weights_to_download(tmp_path)}
    assert w.relpath not in todo                          # skip valid (resume semantics)
    assert len(todo) == 7


def test_prefetch_code_downloads_all_and_resumes(tmp_path):
    code = lw.build_prefetch_code(tmp_path)
    assert "hf_hub_download" in code and lw.HF_REPO_ID in code
    for w in lw.LIVEPORTRAIT_WEIGHTS:
        assert w.relpath in code


# --------------------------------------------------------------- adapter
def _fake_repo(tmp_path, weights_valid=True):
    repo = tmp_path / "liveportrait"
    repo.mkdir()
    (repo / "inference.py").write_text("# fake")
    if weights_valid:
        for w in lw.LIVEPORTRAIT_WEIGHTS:
            _write_weight(repo, w, w.expected_bytes)
    return repo


def test_adapter_required_paths_include_every_weight(tmp_path):
    repo = _fake_repo(tmp_path)
    a = LivePortraitAdapter(device="cpu", config={"repo_dir": repo})
    req = {str(p) for p in a.required_paths()}
    assert str(repo / "inference.py") in req
    for w in lw.LIVEPORTRAIT_WEIGHTS:
        assert str(lw.pretrained_root(repo) / w.relpath) in req


def test_adapter_reports_missing_weight_not_just_dir(tmp_path):
    repo = _fake_repo(tmp_path, weights_valid=False)  # inference.py only
    a = LivePortraitAdapter(device="cpu", config={"repo_dir": repo, "venv_python": sys.executable})
    diag = a.diagnostics()
    assert diag.available is False
    # names the specific missing weight files, not a bare "liveportrait" dir
    assert "missing files" in diag.reason
    assert any(".pth" in ps["path"] or ".onnx" in ps["path"]
               for ps in diag.required_paths if not ps["exists"])


def test_adapter_weights_present_blocks_only_on_packages(tmp_path):
    repo = _fake_repo(tmp_path, weights_valid=True)
    a = LivePortraitAdapter(device="cpu", config={"repo_dir": repo, "venv_python": sys.executable})
    diag = a.diagnostics()
    # All files present -> the remaining blocker is the ML packages (insightface),
    # not weights. (On a real LivePortrait venv those import and it is available.)
    assert all(ps["exists"] for ps in diag.required_paths)
    assert diag.available is False
    assert "missing packages" in diag.reason


def test_adapter_weight_report(tmp_path):
    repo = _fake_repo(tmp_path, weights_valid=True)
    a = LivePortraitAdapter(device="cpu", config={"repo_dir": repo})
    rep = a.weight_report()
    assert len(rep) == 8 and all(r["status"] == "validated" for r in rep)


# --------------------------------------------------------------- driving-video plumbing
_SCENARIOS = ("neutral-intro-en", "neutral-pricing-en")


def _assets(tmp_path, with_video: bool):
    from foundation.shared_utils.audio_io import generate_sine_wav, write_wav
    adir = tmp_path / "assets"
    adir.mkdir()
    for sid in _SCENARIOS:
        write_wav(adir / f"{sid}.wav", generate_sine_wav(3.0, 220.0))
    if with_video:
        (adir / "driving_video.mp4").write_bytes(b"\0" * 1024)  # existence is enough here
    return adir


def _cfg(tmp_path, adir):
    return AvatarBenchmarkConfig(
        adapters=["liveportrait"], assets_dir=str(adir), max_scenarios=2,
        output_dir=str(tmp_path / "runs"), allow_placeholder_assets=True,
        validate_audio=False, monitor_resources=False,
    )


def test_liveportrait_skipped_without_driving_video(tmp_path):
    cfg = _cfg(tmp_path, _assets(tmp_path, with_video=False))
    cases = AvatarBenchmark(cfg).build_cases(tmp_path / "run")
    assert cases and all(c.skip_reason and "driving video" in c.skip_reason for c in cases)


def test_liveportrait_not_skipped_with_driving_video(tmp_path):
    cfg = _cfg(tmp_path, _assets(tmp_path, with_video=True))
    cases = AvatarBenchmark(cfg).build_cases(tmp_path / "run")
    assert cases and all(c.skip_reason is None for c in cases)
    assert all(c.assets.driving_video is not None for c in cases)


def test_sadtalker_ignores_driving_video_requirement(tmp_path):
    # Audio-driven model has no driving-video requirement -> never skipped for it.
    adir = _assets(tmp_path, with_video=False)
    cfg = AvatarBenchmarkConfig(
        adapters=["sadtalker"], assets_dir=str(adir), max_scenarios=2,
        output_dir=str(tmp_path / "runs"), allow_placeholder_assets=True,
        validate_audio=False, monitor_resources=False,
    )
    cases = AvatarBenchmark(cfg).build_cases(tmp_path / "run")
    assert all("driving video" not in (c.skip_reason or "") for c in cases)


# --------------------------------------------------------------- comparison
def _run_with(model, gen, rtf):
    run = RunResult(run_id="r", title="t")
    c = CaseResult(case_id=f"{model}-s", subject_id=model, scenario="neutral_speech",
                   status=CaseStatus.PASSED)
    c.add(Measurement("generation_time_s", gen, "s"))
    c.add(Measurement("real_time_factor", rtf, "x"))
    c.add(Measurement("peak_gpu_mem_mb", 2000, "MB"))
    c.add(Measurement("device", "cuda"))
    run.cases.append(c)
    return run


def test_comparison_includes_both_models():
    summaries = build_comparison([_run_with("sadtalker", 40, 4.8),
                                  _run_with("liveportrait", 12, 1.5)])
    by = {s.model_id: s for s in summaries}
    assert set(by) == {"sadtalker", "liveportrait"}
    assert by["liveportrait"].metrics["generation_time_s"] == 12
    assert by["sadtalker"].success_rate == 1.0


def test_liveportrait_registered_and_real():
    a = create_adapter("liveportrait")
    assert a.RUNS_IN_VENV is True
    assert "driving_video" in a.REQUIRED_INPUTS
