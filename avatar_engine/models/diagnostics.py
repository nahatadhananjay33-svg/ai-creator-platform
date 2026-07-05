"""Adapter runtime diagnostics (Phase A3.7).

Explains **why** an avatar adapter is or is not runnable, replacing a bare
``available=False``.

Real avatar adapters run inside their own per-model venv (they dispatch
inference to ``.venvs/<model>/`` via subprocess). So the dependency / CUDA
probe must execute **inside that venv's interpreter**, not the process that
launched the benchmark. Running the check in the launcher was the Phase A3.6
bug: on Colab the benchmark ran in the main kernel, where ``face_alignment``
/ ``insightface`` are not installed, so every adapter reported unavailable
even though its venv was healthy.

This module runs a tiny JSON-emitting probe in a target interpreter and
assembles a structured, serializable :class:`AdapterDiagnostic`. It is pure
(no adapter imports) so it can be unit-tested directly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

from foundation.logging import get_logger
from foundation.shared_utils.timing import Stopwatch, utc_now_iso

logger = get_logger("avatar_engine.models.diagnostics")

_PROBE_TIMEOUT_S = 180
_SYS_PATH_LIMIT = 20


def _flat(text: str) -> str:
    """Collapse whitespace/newlines so a message is safe in a one-line context
    (log line, markdown table cell)."""
    return " ".join(text.split())


@dataclass
class PackageProbe:
    """Result of importing one declared dependency in the target interpreter."""

    name: str
    importable: bool
    version: str | None = None
    error: str | None = None  # import traceback (last line), truncated


@dataclass
class AdapterDiagnostic:
    """Structured answer to 'can this adapter run, and if not, why?'."""

    model_id: str
    available: bool
    reason: str
    runs_in_venv: bool
    python_executable: str | None
    venv_dir: str | None
    venv_exists: bool
    sys_prefix: str | None = None
    sys_path_head: list[str] = field(default_factory=list)
    packages: list[PackageProbe] = field(default_factory=list)
    torch_installed: bool = False
    torch_version: str | None = None
    torch_cuda_available: bool = False
    torch_cuda_build: str | None = None  # CUDA runtime version torch was built against
    cuda_device_name: str | None = None
    cuda_total_mem_mb: float | None = None
    expected_device: str = "auto"
    actual_device: str = "cpu"  # device inference will actually use in this venv
    cuda_expected: bool = False
    device_matches_expectation: bool = True
    required_paths: list[dict[str, Any]] = field(default_factory=list)  # {path, exists}
    warnings: list[str] = field(default_factory=list)
    probe_error: str | None = None
    probe_duration_s: float | None = None
    checked_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- env
def sanitized_subprocess_env(venv_dir: Path | None) -> dict[str, str]:
    """``os.environ`` minus leakage from the launcher's own environment.

    Invoking ``.venvs/<m>/bin/python`` uses that interpreter's site-packages,
    but a stray ``PYTHONPATH`` / ``PYTHONHOME`` / ``VIRTUAL_ENV`` inherited
    from the launching process can shadow them and import the wrong torch.
    Strip those, then re-point ``VIRTUAL_ENV`` at the target venv so tools
    that read it behave. (Addresses A3.7 requirement: subprocesses must
    inherit the *correct* environment.)
    """
    dropped = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "PYTHONSTARTUP", "CONDA_PREFIX")
    env = {k: v for k, v in os.environ.items() if k not in dropped}
    if venv_dir is not None:
        env["VIRTUAL_ENV"] = str(venv_dir)
    return env


# --------------------------------------------------------------------------- probe
# Emits one JSON line describing the interpreter, imports, and torch/CUDA state.
_PROBE_CODE = (
    "import json, sys, importlib\n"
    "packages = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []\n"
    "out = {'executable': sys.executable, 'prefix': sys.prefix, "
    "'sys_path': sys.path[:%d], 'packages': [], 'torch': None}\n"
    "for name in packages:\n"
    "    e = {'name': name, 'importable': False, 'version': None, 'error': None}\n"
    "    try:\n"
    "        m = importlib.import_module(name)\n"
    "        e['importable'] = True\n"
    "        e['version'] = getattr(m, '__version__', None)\n"
    "    except BaseException as ex:\n"
    "        import traceback\n"
    "        e['error'] = ''.join(traceback.format_exception_only(type(ex), ex)).strip()[:500]\n"
    "    out['packages'].append(e)\n"
    "try:\n"
    "    import torch\n"
    "    t = {'installed': True, 'version': torch.__version__, "
    "'cuda_available': bool(torch.cuda.is_available()), "
    "'cuda_build': getattr(torch.version, 'cuda', None), 'device_name': None, "
    "'total_mem_mb': None}\n"
    "    try:\n"
    "        if torch.cuda.is_available():\n"
    "            t['device_name'] = torch.cuda.get_device_name(0)\n"
    "            t['total_mem_mb'] = torch.cuda.get_device_properties(0).total_memory / (1024*1024)\n"
    "    except BaseException:\n"
    "        pass\n"
    "    out['torch'] = t\n"
    "except BaseException:\n"
    "    out['torch'] = {'installed': False}\n"
    "print(json.dumps(out))\n"
) % _SYS_PATH_LIMIT


def run_env_probe(
    python_exe: Path | str,
    packages: Sequence[str],
    venv_dir: Path | None = None,
    timeout_s: int = _PROBE_TIMEOUT_S,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Run the probe in ``python_exe``. Returns (data, error, duration_s)."""
    cmd = [str(python_exe), "-c", _PROBE_CODE, json.dumps(list(packages))]
    with Stopwatch() as sw:
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s,
                env=sanitized_subprocess_env(venv_dir),
                encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, _flat(f"{type(exc).__name__}: {exc}")[:500], round(sw.elapsed_s, 2)
    if proc.returncode != 0:
        tail = _flat((proc.stderr or proc.stdout or ""))[-600:]
        return None, f"probe exited {proc.returncode}: {tail}", round(sw.elapsed_s, 2)
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None, "probe produced no output", round(sw.elapsed_s, 2)
    try:
        return json.loads(lines[-1]), None, round(sw.elapsed_s, 2)
    except json.JSONDecodeError:
        return None, _flat(f"probe output not JSON: {lines[-1][:300]}"), round(sw.elapsed_s, 2)


# --------------------------------------------------------------------------- assemble
def diagnose(
    model_id: str,
    *,
    packages: Sequence[str],
    required_paths: Sequence[Path],
    expected_device: str,
    runs_in_venv: bool,
    venv_python: Path,
    venv_dir: Path,
) -> AdapterDiagnostic:
    """Build a full diagnostic for one adapter (pure; no adapter import)."""
    cuda_expected = expected_device == "cuda"
    path_states = [{"path": str(p), "exists": Path(p).exists()} for p in required_paths]
    missing_paths = [ps["path"] for ps in path_states if not ps["exists"]]

    # Decide which interpreter answers the dependency/CUDA questions.
    if runs_in_venv:
        target_python: Path | str = venv_python
        venv_exists = Path(venv_python).exists()
    else:
        target_python = sys.executable
        venv_exists = True  # in-process adapters (e.g. mock) need no venv

    diag = AdapterDiagnostic(
        model_id=model_id,
        available=False,
        reason="",
        runs_in_venv=runs_in_venv,
        python_executable=str(target_python),
        venv_dir=str(venv_dir),
        venv_exists=venv_exists,
        expected_device=expected_device,
        cuda_expected=cuda_expected,
        required_paths=path_states,
    )

    # In-process adapter with no declared deps or files (e.g. mock): it runs in
    # the current interpreter and needs nothing external — answer without a probe.
    if not runs_in_venv and not packages and not required_paths:
        diag.available = True
        diag.sys_prefix = sys.prefix
        diag.reason = "ready (in-process adapter; no external dependencies)"
        _log(diag)
        return diag

    # Missing venv is a terminal, self-explanatory failure — skip the probe.
    if runs_in_venv and not venv_exists:
        diag.reason = (
            f"venv not found at {venv_dir} — run "
            f"`python -m avatar_engine.scripts.install_models --models {model_id}`"
        )
        _log(diag)
        return diag

    data, probe_err, dur = run_env_probe(target_python, packages, venv_dir)
    diag.probe_duration_s = dur
    diag.probe_error = probe_err

    if data is None:
        diag.reason = f"environment probe failed: {probe_err}"
        _log(diag)
        return diag

    diag.sys_prefix = data.get("prefix")
    diag.sys_path_head = list(data.get("sys_path", []))[:_SYS_PATH_LIMIT]
    diag.python_executable = data.get("executable", diag.python_executable)
    for e in data.get("packages", []):
        diag.packages.append(PackageProbe(
            name=e.get("name", "?"), importable=bool(e.get("importable")),
            version=e.get("version"), error=e.get("error"),
        ))
    torch_info = data.get("torch") or {}
    diag.torch_installed = bool(torch_info.get("installed"))
    diag.torch_version = torch_info.get("version")
    diag.torch_cuda_available = bool(torch_info.get("cuda_available"))
    diag.torch_cuda_build = torch_info.get("cuda_build")
    diag.cuda_device_name = torch_info.get("device_name")
    diag.cuda_total_mem_mb = torch_info.get("total_mem_mb")

    # Actual device inference will use: CUDA only if requested *and* usable here.
    diag.actual_device = "cuda" if (cuda_expected and diag.torch_cuda_available) else "cpu"
    diag.device_matches_expectation = (not cuda_expected) or diag.torch_cuda_available
    if cuda_expected and not diag.torch_cuda_available:
        diag.warnings.append(
            "expected CUDA device but torch.cuda.is_available() is False in this "
            "venv — inference will fall back to CPU or fail"
        )

    missing_pkgs = [p.name for p in diag.packages if not p.importable]

    # Availability = deps import + required files present. (Device mismatch is
    # a warning, not a blocker: the model can still produce output on CPU.)
    diag.available = not missing_pkgs and not missing_paths

    if diag.available:
        cuda_note = (
            f"cuda={diag.cuda_device_name}" if diag.torch_cuda_available
            else "cuda=unavailable(cpu)"
        )
        diag.reason = f"ready ({cuda_note}; torch={diag.torch_version or 'n/a'})"
    else:
        bits = []
        if missing_pkgs:
            bits.append("missing packages: " + ", ".join(missing_pkgs))
        if missing_paths:
            bits.append("missing files: " + ", ".join(Path(p).name for p in missing_paths))
        diag.reason = "; ".join(bits)
    _log(diag)
    return diag


def _log(diag: AdapterDiagnostic) -> None:
    logger.info(
        "Adapter diagnostic",
        extra={"context": {
            "engine": diag.model_id,
            "available": diag.available,
            "reason": diag.reason,
            "python": diag.python_executable,
            "venv_exists": diag.venv_exists,
            "torch": diag.torch_version,
            "cuda_available": diag.torch_cuda_available,
            "device_expected": diag.expected_device,
            "device_matches": diag.device_matches_expectation,
        }},
    )


# --------------------------------------------------------------------------- report
def write_adapter_validation_report(
    diags: Sequence[AdapterDiagnostic], out_dir: Path
) -> dict[str, Path]:
    """Write ``adapter_validation_report.{json,md}`` for a set of diagnostics."""
    from foundation.shared_utils.hardware import probe_hardware

    out_dir.mkdir(parents=True, exist_ok=True)
    hw = probe_hardware()
    generated_at = utc_now_iso()

    json_path = out_dir / "adapter_validation_report.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "host": hw.to_dict(),
                "adapters": [d.to_dict() for d in diags],
            },
            ensure_ascii=False, indent=2, default=str,
        ),
        encoding="utf-8",
    )

    gpu = ", ".join(f"{g.name} ({(g.vram_total_mb or 0)//1024} GB)" for g in hw.gpus) or "none"
    lines = [
        "# Adapter Validation Report", "",
        f"Generated: {generated_at}", "",
        f"Host: {hw.os_name} · {hw.cpu_cores_logical} cores · "
        f"{round((hw.ram_total_mb or 0)/1024,1)} GB RAM · GPU: {gpu}", "",
        "Each adapter's dependencies and CUDA state are probed **inside its own "
        "venv interpreter**, not the launcher — so `available` reflects the model's "
        "isolated environment.", "",
        "## Summary", "",
        "| Adapter | Available | Device✓ | Reason |",
        "|---|---|---|---|",
    ]
    for d in diags:
        dev = "n/a" if not d.cuda_expected else ("yes" if d.device_matches_expectation else "**NO**")
        lines.append(
            f"| {d.model_id} | {'✅' if d.available else '❌'} | {dev} | {_flat(d.reason)} |"
        )
    lines.append("")
    lines.append("## Per-adapter detail")
    for d in diags:
        lines += [
            "", f"### {d.model_id} — {'AVAILABLE' if d.available else 'UNAVAILABLE'}", "",
            f"- Reason: {d.reason}",
            f"- Runs in venv: {d.runs_in_venv}  ·  venv exists: {d.venv_exists}",
            f"- Python executable: `{d.python_executable}`",
            f"- venv dir: `{d.venv_dir}`",
            f"- torch: {d.torch_version or 'not installed'}  ·  "
            f"cuda_available: {d.torch_cuda_available}  ·  "
            f"cuda_build: {d.torch_cuda_build or 'n/a'}  ·  GPU: {d.cuda_device_name or 'none'}"
            + (f" ({d.cuda_total_mem_mb/1024:.1f} GB)" if d.cuda_total_mem_mb else ""),
            f"- expected device: {d.expected_device}  ·  actual: {d.actual_device}  ·  "
            f"matches: {d.device_matches_expectation}",
        ]
        if d.packages:
            lines.append("- Packages:")
            for p in d.packages:
                mark = "ok" if p.importable else f"FAIL — {p.error}"
                lines.append(f"    - `{p.name}` {('('+p.version+')') if p.version else ''}: {mark}")
        if d.required_paths:
            lines.append("- Required files:")
            for ps in d.required_paths:
                lines.append(f"    - {'present' if ps['exists'] else 'MISSING'}: `{ps['path']}`")
        for w in d.warnings:
            lines.append(f"- ⚠️ {w}")
        if d.probe_error:
            lines.append(f"- Probe error: {d.probe_error}")
    md_path = out_dir / "adapter_validation_report.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
