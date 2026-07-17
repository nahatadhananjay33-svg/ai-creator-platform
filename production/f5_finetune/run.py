"""T3 orchestrator — the one command that makes fine-tuning a one-liner.

    python -m production.f5_finetune.run              # transcribe + prepare + dry-run plan
    python -m production.f5_finetune.run --start      # ...and actually start training
    python -m production.f5_finetune.run --skip-transcribe   # reuse existing transcripts

Stage dispatch mirrors voice_engine/scripts/setup_benchmark.py: transcription,
dataset prep and evaluation run inside the f5-tts model venv; this driver only
sequences them and streams logs to <workspace>/logs/.

Training itself is NEVER started without --start (T3 requirement).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from production.f5_finetune.common import (  # noqa: E402
    load_config, run_streamed, venv_python, workspace_dir,
)
from production.f5_finetune.launch import main as launch_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F5 fine-tuning pipeline")
    parser.add_argument("--start", action="store_true", help="Start training after prep")
    parser.add_argument("--skip-transcribe", action="store_true",
                        help="Reuse existing workspace transcripts")
    parser.add_argument("--transcribe-limit", type=int, default=0,
                        help="Debug: only transcribe N segments")
    args = parser.parse_args(argv)

    cfg = load_config()
    python = venv_python(cfg)
    if not python.exists():
        print(f"[run] FAIL — f5-tts venv missing ({python}). Run "
              "`python -m voice_engine.scripts.setup_benchmark --model f5-tts` first.")
        return 1
    logs = workspace_dir(cfg) / "logs"
    ts = time.strftime("%Y%m%d-%H%M%S")
    meta_csv = workspace_dir(cfg) / "transcripts" / "metadata.csv"

    if args.skip_transcribe and not meta_csv.exists():
        print(f"[run] FAIL — --skip-transcribe but {meta_csv} does not exist.")
        return 1
    if not args.skip_transcribe:
        cmd = [str(python), "-m", "production.f5_finetune.transcribe"]
        if args.transcribe_limit:
            cmd += ["--limit", str(args.transcribe_limit)]
        print("[run] stage 1/3 — transcribe", flush=True)
        if run_streamed(cmd, logs / f"transcribe_{ts}.log") != 0:
            return 1

    print("[run] stage 2/3 — prepare dataset", flush=True)
    if run_streamed([str(python), "-m", "production.f5_finetune.prepare"],
                    logs / f"prepare_{ts}.log") != 0:
        return 1

    print("[run] stage 3/3 — launch" + ("" if args.start else " (dry-run)"), flush=True)
    rc = launch_main(["--start"] if args.start else [])
    if rc == 0 and args.start:
        print("[run] training finished or stopped — evaluate checkpoints with:\n"
              f"  {python} -m production.f5_finetune.evaluate\n"
              "(or run it with --watch in a second process during training).")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
