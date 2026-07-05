"""Shared install-CLI driver used by every engine's install script.

Extracted in Phase A3.5 so the voice and avatar installers share one
implementation (environment probe, compatibility verdicts, install loop,
report writing). Engine scripts stay thin: they pass their INSTALL_SPECS,
a ModelSpec lookup, and an output directory.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Mapping

from foundation.constants.paths import ensure_dir
from foundation.logging import configure_logging
from foundation.model_manager.environment import (
    CompatibilityVerdict,
    EnvironmentReport,
    check_compatibility,
    probe_environment,
)
from foundation.model_manager.installer import InstallationManager, InstallResult, InstallSpec
from foundation.model_manager.spec import ModelSpec
from foundation.shared_utils.timing import utc_now_iso


def write_install_reports(
    env: EnvironmentReport,
    verdicts: list[CompatibilityVerdict],
    results: list[InstallResult],
    output_dir: Path,
    title: str = "Model Installation Report",
) -> Path:
    out = ensure_dir(output_dir)
    payload = {
        "generated_at": utc_now_iso(),
        "environment": env.to_dict(),
        "compatibility": [v.__dict__ for v in verdicts],
        "installs": [r.to_dict() for r in results],
    }
    (out / "installation_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    hw = env.hardware
    gpu = ", ".join(
        f"{g.name} ({(g.vram_total_mb or 0) // 1024} GB)" for g in hw.gpus
    ) or "none detected via torch/nvidia-smi"
    lines = [
        f"# {title}", "", f"Generated: {payload['generated_at']}", "",
        "## Environment", "",
        f"- OS: {env.os_details}",
        f"- CPU: {hw.cpu_name} ({hw.cpu_cores_logical} logical cores)",
        f"- RAM: {round((hw.ram_total_mb or 0) / 1024, 1)} GB",
        f"- GPU: {gpu}",
        f"- NVIDIA driver: {env.nvidia_driver.driver_version or 'n/a'}"
        + (f" — {env.nvidia_driver.notes}" if env.nvidia_driver.notes else ""),
        f"- CUDA usable by modern PyTorch: **{'yes' if env.cuda_usable else 'no'}**",
        f"- Host Python: {env.python_version}",
        f"- Free disk: {env.disk_free_gb} GB",
        "", "## Compatibility verdicts", "",
        "| Model | Compatible | Mode | Reasons |", "|---|---|---|---|",
    ]
    for v in verdicts:
        lines.append(
            f"| {v.model_id} | {'yes' if v.compatible else 'NO'} | {v.mode} | "
            f"{'; '.join(v.reasons) or '—'} |"
        )
    if results:
        lines += ["", "## Installation results", "",
                  "| Model | Status | Time (s) | Verified imports | Torch | Repo | Error |",
                  "|---|---|---|---|---|---|---|"]
        for r in results:
            lines.append(
                f"| {r.model_id} | **{r.status}** | {r.duration_s} | "
                f"{', '.join(r.verified_imports) or '—'} | {r.torch_version or '—'} | "
                f"{Path(r.repo_dir).name if r.repo_dir else '—'} | {(r.error or '—')[:160]} |"
            )
    path = out / "installation_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run_install_cli(
    install_specs: Mapping[str, InstallSpec],
    model_spec_lookup: Callable[[str], ModelSpec | None],
    output_dir: Path,
    description: str,
    argv: list[str] | None = None,
) -> int:
    """Standard install CLI: --models/--all/--force/--report-only."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--models", nargs="+", choices=sorted(install_specs))
    parser.add_argument("--all", action="store_true", help="Install every defined model")
    parser.add_argument("--force", action="store_true", help="Reinstall even if verified")
    parser.add_argument("--report-only", action="store_true",
                        help="Probe environment + compatibility, install nothing")
    args = parser.parse_args(argv)

    configure_logging()
    env = probe_environment()
    verdicts = []
    for model_id in install_specs:
        spec = model_spec_lookup(model_id)
        if spec is not None:
            verdicts.append(check_compatibility(spec, env))

    targets = sorted(install_specs) if args.all else (args.models or [])
    results: list[InstallResult] = []
    if not args.report_only:
        manager = InstallationManager()
        for model_id in targets:
            print(f"[install] {model_id} ...", flush=True)
            result = manager.install(install_specs[model_id], env, force=args.force)
            print(f"[install] {model_id}: {result.status}"
                  + (f" — {result.error[:120]}" if result.error else ""), flush=True)
            results.append(result)

    report = write_install_reports(env, verdicts, results, output_dir)
    print(f"\nReport: {report}")
    return 0 if all(
        r.status in ("installed", "already-installed", "skipped") for r in results
    ) else 1
