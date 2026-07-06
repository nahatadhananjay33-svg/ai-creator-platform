"""Regression tests for the Phase A3.7 adapter validation pipeline.

These pin the behaviour that A3.6 lacked: adapters must report *why* they are
unavailable (missing venv / package / checkpoint / probe failure), the
dependency probe must run in the target interpreter, and subprocess env must
be sanitized. Deterministic on any host (no GPU / model venvs needed) via
config overrides.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from foundation.exceptions import AdapterNotAvailableError
from foundation.model_manager.installer import model_venv_python
from avatar_engine.models import ADAPTER_CLASSES, create_adapter
from avatar_engine.models.diagnostics import (
    AdapterDiagnostic,
    diagnose,
    run_env_probe,
    sanitized_subprocess_env,
    write_adapter_validation_report,
)
from avatar_engine.models.mock import MockAvatarAdapter
from avatar_engine.models.sadtalker import SadTalkerAdapter
from avatar_engine.models.validation import AvatarModelValidator

_MISSING = "no_such_package_zzz_12345"


# --------------------------------------------------------------- env sanitation
def test_sanitized_env_strips_launcher_leakage(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "/leak/site-packages")
    monkeypatch.setenv("VIRTUAL_ENV", "/leak/venv")
    monkeypatch.setenv("PYTHONHOME", "/leak/home")
    env = sanitized_subprocess_env(Path("/target/venv"))
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert env["VIRTUAL_ENV"] == str(Path("/target/venv"))


def test_sanitized_env_no_venv_dir(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    env = sanitized_subprocess_env(None)
    assert "VIRTUAL_ENV" not in env


# --------------------------------------------------------------- venv path
def test_model_venv_python_convention():
    p = model_venv_python("demo")
    assert p.parent.parent.name == "demo"
    assert p.name in ("python", "python.exe")


# --------------------------------------------------------------- probe
def test_run_env_probe_reports_imports_and_torch():
    data, err, dur = run_env_probe(sys.executable, ["json", _MISSING])
    assert err is None, err
    assert data is not None
    by_name = {p["name"]: p for p in data["packages"]}
    assert by_name["json"]["importable"] is True
    assert by_name[_MISSING]["importable"] is False
    assert by_name[_MISSING]["error"]  # traceback captured
    assert "torch" in data  # present whether or not torch is installed
    assert isinstance(dur, float)


def test_run_env_probe_bad_interpreter():
    data, err, _ = run_env_probe(Path("/no/such/python-xyz"), ["json"])
    assert data is None
    assert err and "\n" not in err  # single-line, table-safe


# --------------------------------------------------------------- diagnose()
def test_diagnose_missing_venv():
    d = diagnose(
        "ghost", packages=("torch",), required_paths=[], expected_device="cpu",
        runs_in_venv=True, venv_python=Path("/no/such/py"), venv_dir=Path("/no/such"),
    )
    assert d.available is False
    assert d.venv_exists is False
    assert "venv not found" in d.reason


def test_diagnose_missing_package_named_in_reason():
    # venv "exists" (point at the current interpreter); the missing package drives it.
    d = diagnose(
        "probe", packages=(_MISSING,), required_paths=[], expected_device="cpu",
        runs_in_venv=True, venv_python=Path(sys.executable),
        venv_dir=Path(sys.executable).parent,
    )
    assert d.available is False
    assert _MISSING in d.reason
    assert any(not p.importable for p in d.packages)


def test_diagnose_missing_required_file(tmp_path):
    missing = tmp_path / "weights.safetensors"
    d = diagnose(
        "probe", packages=(), required_paths=[missing], expected_device="cpu",
        runs_in_venv=True, venv_python=Path(sys.executable),
        venv_dir=Path(sys.executable).parent,
    )
    assert d.available is False
    assert "missing files" in d.reason
    assert d.required_paths[0]["exists"] is False


def test_diagnose_available_when_all_present(tmp_path):
    present = tmp_path / "ok.txt"
    present.write_text("x")
    d = diagnose(
        "probe", packages=("json",), required_paths=[present], expected_device="cpu",
        runs_in_venv=True, venv_python=Path(sys.executable),
        venv_dir=Path(sys.executable).parent,
    )
    assert d.available is True
    assert "ready" in d.reason


def test_diagnose_cuda_mismatch_is_warning_not_blocker(tmp_path):
    # Expect CUDA but the (current) interpreter almost certainly has no GPU torch:
    # availability stays True (deps ok) while a warning records the mismatch.
    d = diagnose(
        "probe", packages=("json",), required_paths=[], expected_device="cuda",
        runs_in_venv=True, venv_python=Path(sys.executable),
        venv_dir=Path(sys.executable).parent,
    )
    if not d.torch_cuda_available:
        assert d.available is True
        assert d.device_matches_expectation is False
        assert any("CUDA" in w for w in d.warnings)


# --------------------------------------------------------------- adapters
def test_mock_available_in_process():
    adapter = MockAvatarAdapter()
    diag = adapter.diagnostics()
    assert diag.available is True
    assert diag.runs_in_venv is False
    assert adapter.is_available() is True


def test_planned_adapter_reports_not_implemented():
    adapter = create_adapter("echomimic-v3")  # still a planned placeholder
    diag = adapter.diagnostics()
    assert diag.available is False
    assert "planned" in diag.reason.lower()
    assert adapter.is_available() is False


def test_planned_adapter_load_raises_skippable():
    adapter = create_adapter("echomimic-v3")
    with pytest.raises(AdapterNotAvailableError):
        adapter.load()


def test_sadtalker_reports_missing_packages_when_files_present(tmp_path):
    # Fake a complete repo/checkpoint layout; point the venv at this interpreter.
    repo = tmp_path / "repo"
    (repo / "checkpoints").mkdir(parents=True)
    (repo / "inference.py").write_text("# fake")
    (repo / "checkpoints" / "SadTalker_V0.0.2_256.safetensors").write_text("w")
    adapter = SadTalkerAdapter(
        device="cpu", config={"repo_dir": repo, "venv_python": sys.executable}
    )
    diag = adapter.diagnostics()
    # Files are present; the (absent) ML packages must be the stated reason.
    assert all(ps["exists"] for ps in diag.required_paths)
    assert diag.available is False
    assert "missing packages" in diag.reason


def test_unavailable_adapter_load_raises_with_reason(tmp_path):
    adapter = SadTalkerAdapter(
        device="cpu",
        config={"repo_dir": tmp_path / "nope", "venv_python": "/no/such/py"},
    )
    with pytest.raises(AdapterNotAvailableError) as excinfo:
        adapter.load()
    assert "unavailable" in str(excinfo.value)


# --------------------------------------------------------------- validator + report
def test_validator_records_diagnostic_reason():
    validator = AvatarModelValidator(Path.cwd() / "avatar_engine" / "output" / "validation")
    result = validator.validate(create_adapter("echomimic-v3"))  # still planned
    assert result.dependencies_ok is False
    assert result.diagnostics is not None
    assert "planned" in (result.error or "").lower()


def test_write_report_creates_md_and_json(tmp_path):
    diags = [
        AdapterDiagnostic(
            model_id="demo", available=True, reason="ready", runs_in_venv=False,
            python_executable=sys.executable, venv_dir=None, venv_exists=True,
        )
    ]
    reports = write_adapter_validation_report(diags, tmp_path)
    assert reports["json"].exists() and reports["markdown"].exists()
    payload = json.loads(reports["json"].read_text(encoding="utf-8"))
    assert payload["adapters"][0]["model_id"] == "demo"
    assert "Adapter Validation Report" in reports["markdown"].read_text(encoding="utf-8")


def test_default_and_planned_adapters_registered():
    for mid in ("mock", "sadtalker", "liveportrait", "musetalk", "echomimic-v3"):
        assert mid in ADAPTER_CLASSES
