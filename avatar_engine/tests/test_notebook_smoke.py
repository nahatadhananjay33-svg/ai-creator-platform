"""Smoke test for the Colab notebook (A3.9).

Guards the "fresh Colab -> Run All" contract: the notebook is valid JSON, every
code cell parses, and the key automated steps (install, weight validation,
driving-video seed, CUDA check, benchmark, comparison) are present. Uses only
the stdlib json parser so it runs without nbformat.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

NB = (Path(__file__).resolve().parents[1] / "notebooks" / "phase_a36_gpu_validation.ipynb")


def _cells():
    data = json.loads(NB.read_text(encoding="utf-8"))
    return data["cells"]


def test_notebook_exists_and_parses():
    assert NB.exists(), NB
    data = json.loads(NB.read_text(encoding="utf-8"))
    assert data.get("nbformat") == 4
    assert any(c["cell_type"] == "code" for c in data["cells"])


def test_all_code_cells_compile():
    for i, c in enumerate(_cells()):
        if c["cell_type"] != "code":
            continue
        src = "".join(c["source"]) if isinstance(c["source"], list) else c["source"]
        ast.parse(src)  # raises SyntaxError on a broken cell


def test_run_all_steps_present():
    src = " ".join(
        ("".join(c["source"]) if isinstance(c["source"], list) else c["source"])
        for c in _cells() if c["cell_type"] == "code"
    )
    for step in (
        "install_models",                          # install + weight download
        "validate_liveportrait_weights",           # weight validation
        "driving_video.mp4",                       # driving-clip seed for LivePortrait
        "gpu_install_target",                      # CUDA detection
        "run_benchmark",                           # benchmark execution
        "validate_adapters",                       # adapter diagnostics
        "compare_models",                          # comparison report
    ):
        assert step in src, f"notebook missing step: {step}"


def test_config_is_first_editable_cell():
    # The single cell a user edits between runs must exist and hold CONFIG.
    src = " ".join(
        ("".join(c["source"]) if isinstance(c["source"], list) else c["source"])
        for c in _cells() if c["cell_type"] == "code"
    )
    assert "CONFIG = {" in src and "REPO_URL" in src and "MODELS" in src
