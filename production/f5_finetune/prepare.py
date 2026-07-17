"""Stage 2 — build the F5 training dataset from the transcripts (f5 venv).

    <venv python> -m production.f5_finetune.prepare

1. Materializes the pretrained Emilia vocab where prepare_csv_wavs expects it
   (pip installs of f5-tts do not ship data/Emilia_ZH_EN_pinyin/vocab.txt; the
   identical vocab ships as f5_tts/infer/examples/vocab.txt).
2. Hard-verifies every transcript character is covered by that vocab (the
   text embedding cannot learn chars that do not exist in it).
3. Runs the packaged prepare_csv_wavs in FINETUNE mode -> raw.arrow,
   duration.json and the pretrained vocab.txt under data/<dataset>_pinyin.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from production.f5_finetune.common import load_config, workspace_dir  # noqa: E402


def pretrained_vocab() -> tuple[Path, set[str]]:
    base = Path(str(files("f5_tts").joinpath("../.."))).resolve()
    canonical = base / "data" / "Emilia_ZH_EN_pinyin" / "vocab.txt"
    if not canonical.exists():
        shipped = Path(str(files("f5_tts").joinpath("infer/examples/vocab.txt")))
        canonical.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(shipped, canonical)
        print(f"[prepare] materialized pretrained vocab -> {canonical}")
    vocab = {line.rstrip("\n") for line in canonical.read_text(encoding="utf-8").splitlines()}
    return canonical, vocab


def main() -> int:
    cfg = load_config()
    meta_csv = workspace_dir(cfg) / "transcripts" / "metadata.csv"
    if not meta_csv.exists():
        print(f"[prepare] FAIL — run transcribe first; missing {meta_csv}")
        return 1

    _, vocab = pretrained_vocab()
    bad: dict[str, list[str]] = {}
    covered_lines: list[str] = []
    lines = meta_csv.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        audio, _, text = line.partition("|")
        missing = sorted({ch for ch in text if ch not in vocab and ch != " "})
        if missing:
            bad[Path(audio).name] = missing
        else:
            covered_lines.append(line)
    n_rows = len(lines) - 1
    charset_report = workspace_dir(cfg) / "transcripts" / "charset_report.json"
    charset_report.write_text(json.dumps(
        {"rows": n_rows, "rows_with_uncovered_chars": len(bad), "detail": bad},
        indent=2, ensure_ascii=False), encoding="utf-8")
    if bad:
        uncovered = sorted({c for chars in bad.values() for c in chars})
        # A systematic romanization gap (like the candra-O incident: 177/521
        # rows) must be fixed at the source; a handful of odd rows are dropped
        # so one stray character cannot block training.
        if len(bad) / max(n_rows, 1) > 0.10:
            print(f"[prepare] FAIL — {len(bad)}/{n_rows} transcripts contain characters "
                  f"outside the pretrained vocab: {''.join(uncovered)!r}\n"
                  f"          see {charset_report}; fix romanization/normalization first.")
            return 1
        meta_csv = meta_csv.with_name("metadata_covered.csv")
        meta_csv.write_text("\n".join([lines[0], *covered_lines]) + "\n", encoding="utf-8")
        print(f"[prepare] charset: dropped {len(bad)}/{n_rows} rows with uncovered chars "
              f"{''.join(uncovered)!r} (see {charset_report.name}); "
              f"{len(covered_lines)} rows remain")
    else:
        print(f"[prepare] charset OK — all {n_rows} transcripts covered by the pretrained vocab")

    base = Path(str(files("f5_tts").joinpath("../.."))).resolve()
    out_dir = base / "data" / f"{cfg['dataset_name']}_{cfg['training']['tokenizer']}"
    script = Path(str(files("f5_tts").joinpath("train/datasets/prepare_csv_wavs.py")))
    cmd = [sys.executable, str(script), str(meta_csv), str(out_dir)]  # no --pretrain = finetune
    print(f"[prepare] {' '.join(cmd)}", flush=True)
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        print(f"[prepare] dataset ready: {out_dir}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
