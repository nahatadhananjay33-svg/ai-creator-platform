"""Stage 3 — build (and optionally run) the fine-tuning command (driver env).

    python -m production.f5_finetune.launch            # dry-run: print the plan
    python -m production.f5_finetune.launch --start    # actually train

Everything is delegated to the packaged trainer (f5_tts.train.finetune_cli via
accelerate): checkpointing (save_per_updates / keep_last_n / last_per_updates),
auto-resume from ckpts/<dataset>/model_last.pt, fp16 mixed precision,
tensorboard logging and per-checkpoint sample audio (--log_samples).

This launcher only adds what the trainer cannot know:
  - persists checkpoints: ckpts/<dataset> is symlinked into the workspace
    (on Colab that is Drive, so runtime disconnects lose nothing);
  - a full stdout/stderr log under <workspace>/logs/;
  - the T2 MPLBACKEND=Agg guard.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from production.f5_finetune.common import (  # noqa: E402
    f5_base_dir, load_config, run_streamed, venv_python, workspace_dir,
)


def build_command(cfg: dict, python: Path) -> list[str]:
    t = cfg["training"]
    finetune_cli = None
    import subprocess

    out = subprocess.run(
        [str(python), "-c", "import f5_tts.train.finetune_cli as m; print(m.__file__)"],
        capture_output=True, text=True, check=True)
    finetune_cli = out.stdout.strip()
    cmd = [str(python), "-m", "accelerate.commands.launch",
           "--mixed_precision", t["mixed_precision"], finetune_cli,
           "--exp_name", cfg["exp_name"],
           "--dataset_name", cfg["dataset_name"],
           "--finetune",
           "--tokenizer", t["tokenizer"],
           "--learning_rate", str(t["learning_rate"]),
           "--batch_size_per_gpu", str(t["batch_size_per_gpu"]),
           "--batch_size_type", t["batch_size_type"],
           "--max_samples", str(t["max_samples"]),
           "--grad_accumulation_steps", str(t["grad_accumulation_steps"]),
           "--epochs", str(t["epochs"]),
           "--num_warmup_updates", str(t["num_warmup_updates"]),
           "--save_per_updates", str(t["save_per_updates"]),
           "--keep_last_n_checkpoints", str(t["keep_last_n_checkpoints"]),
           "--last_per_updates", str(t["last_per_updates"]),
           "--logger", t["logger"]]
    if t.get("log_samples"):
        cmd.append("--log_samples")
    return cmd


def link_checkpoints(cfg: dict, python: Path) -> Path:
    """ckpts/<dataset> -> <workspace>/ckpts/<dataset> (symlink where possible)."""
    base = f5_base_dir(python)
    ckpt_src = base / "ckpts" / cfg["dataset_name"]
    ckpt_dst = workspace_dir(cfg) / "ckpts" / cfg["dataset_name"]
    ckpt_dst.mkdir(parents=True, exist_ok=True)
    if ckpt_src.is_symlink():
        return ckpt_dst
    if ckpt_src.exists():  # real dir already there — leave it, warn
        print(f"[launch] note: {ckpt_src} already exists as a real directory; "
              "checkpoints stay there (not persisted to the workspace).")
        return ckpt_src
    ckpt_src.parent.mkdir(parents=True, exist_ok=True)
    try:
        ckpt_src.symlink_to(ckpt_dst, target_is_directory=True)
        print(f"[launch] checkpoints persisted: {ckpt_src} -> {ckpt_dst}")
    except OSError as exc:  # Windows without dev-mode: fine, training is cloud-only
        print(f"[launch] symlink unavailable ({exc}); checkpoints will stay in {ckpt_src}")
        return ckpt_src
    return ckpt_dst


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch (or plan) F5 fine-tuning")
    parser.add_argument("--start", action="store_true", help="Actually start training")
    args = parser.parse_args(argv)

    cfg = load_config()
    python = venv_python(cfg)
    if not python.exists():
        print(f"[launch] FAIL — f5-tts venv missing ({python}); run setup_benchmark first.")
        return 1
    data_dir = f5_base_dir(python) / "data" / f"{cfg['dataset_name']}_{cfg['training']['tokenizer']}"
    if not (data_dir / "raw.arrow").exists():
        print(f"[launch] FAIL — prepared dataset missing ({data_dir}); run prepare first.")
        return 1

    ckpt_dir = link_checkpoints(cfg, python)
    cmd = build_command(cfg, python)
    print("[launch] training command:\n  " + " ".join(cmd))
    print(f"[launch] dataset:     {data_dir}")
    print(f"[launch] checkpoints: {ckpt_dir} (auto-resume from model_last.pt)")
    if not args.start:
        print("[launch] DRY-RUN — pass --start to begin training.")
        return 0

    log = workspace_dir(cfg) / "logs" / f"train_{time.strftime('%Y%m%d-%H%M%S')}.log"
    print(f"[launch] log: {log}", flush=True)
    return run_streamed(cmd, log)


if __name__ == "__main__":
    raise SystemExit(main())
