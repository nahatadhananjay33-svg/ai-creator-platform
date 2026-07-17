"""Shared helpers for the F5 fine-tuning pipeline (config, paths, dispatch)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def is_colab() -> bool:
    return Path("/content").is_dir()


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = yaml.safe_load((path or CONFIG_PATH).read_text(encoding="utf-8"))
    env = "colab" if is_colab() else "local"
    cfg["env"] = env
    cfg["resolved_paths"] = {k: Path(v) for k, v in cfg["paths"][env].items()}
    return cfg


def workspace_dir(cfg: dict[str, Any]) -> Path:
    ws = cfg["resolved_paths"]["workspace"]
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def dataset_root(cfg: dict[str, Any]) -> Path:
    return cfg["resolved_paths"]["dataset_root"]


def venv_python(cfg: dict[str, Any]) -> Path:
    """Interpreter of the f5-tts model venv (single source of truth reused)."""
    from foundation.model_manager.installer import model_venv_python

    return model_venv_python(cfg["model"])


def f5_base_dir(python: Path) -> Path:
    """The directory f5_tts treats as its data/ckpts base (files('f5_tts')/../..)."""
    out = subprocess.run(
        [str(python), "-c",
         "from importlib.resources import files; print(files('f5_tts').joinpath('../..').resolve())"],
        capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


def run_streamed(cmd: list[str], log_path: Path, cwd: Path | None = None,
                 env_extra: dict[str, str] | None = None) -> int:
    """Run a command, teeing stdout+stderr to console and a log file.

    MPLBACKEND=Agg is always forced: notebook kernels leak an inline backend
    the model venv cannot resolve (T2 lesson).
    """
    env = {**os.environ, "MPLBACKEND": "Agg", "PYTHONUTF8": "1", **(env_extra or {})}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(map(str, cmd))}\n")
        proc = subprocess.Popen(list(map(str, cmd)), cwd=str(cwd or PROJECT_ROOT), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
        log.write(f"[exit {proc.returncode}]\n")
    return proc.returncode


def accepted_rows(cfg: dict[str, Any]) -> list[dict[str, str]]:
    """Accepted-segment rows from the production dataset metadata (read-only)."""
    import csv

    csv_path = dataset_root(cfg) / "metadata" / "dataset.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("accepted") == "1"]
    if not rows:
        raise RuntimeError(f"no accepted rows found in {csv_path}")
    # audio_path column holds the path from the machine that built the dataset;
    # re-anchor on the current dataset root so the manifest is portable.
    for r in rows:
        r["resolved_audio"] = str(dataset_root(cfg) / "accepted_segments" / r["segment_file"])
    return rows
