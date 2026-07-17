"""Stage 4 — objective per-checkpoint evaluation (runs inside the f5 venv).

    <venv python> -m production.f5_finetune.evaluate            # eval new ckpts once
    <venv python> -m production.f5_finetune.evaluate --watch    # poll during training

For every checkpoint in ckpts/<dataset>/ not yet evaluated:
  - synthesize the fixed eval prompts (config) with the auto-picked reference
    (highest-SNR accepted segment + its stage-1 transcript);
  - metrics per prompt: audio duration, ASR round-trip similarity
    (faster-whisper -> difflib ratio vs the prompt), and speaker similarity
    vs the reference when resemblyzer is available
    (voice_engine.metrics.SpeakerSimilarityMetric — skips gracefully);
  - artifacts: <workspace>/eval/<ckpt>/prompt<i>.wav + metrics.csv row.

State lives in <workspace>/eval/evaluated.json, so this is safe to re-run and
to leave polling next to a live training run.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from production.f5_finetune.common import accepted_rows, load_config, workspace_dir  # noqa: E402
from production.f5_finetune.transcribe import romanize  # noqa: E402


def pick_reference(cfg: dict) -> tuple[Path, str]:
    """Highest-SNR accepted segment + its transcript from stage 1."""
    rows = sorted(accepted_rows(cfg), key=lambda r: float(r["snr_db"]), reverse=True)
    tr_csv = workspace_dir(cfg) / "transcripts" / "transcripts.csv"
    texts: dict[str, str] = {}
    if tr_csv.exists():
        with open(tr_csv, encoding="utf-8") as f:
            for rec in csv.DictReader(f):
                texts[rec["segment_file"]] = rec["text"]
    for r in rows:
        text = texts.get(r["segment_file"], "")
        if text:
            return Path(r["resolved_audio"]), text
    raise RuntimeError("no reference with a transcript found — run transcribe first")


def asr_similarity(model, wav: Path, expected: str) -> float:
    segments, _ = model.transcribe(str(wav), vad_filter=False)
    got = romanize(" ".join(s.text.strip() for s in segments)).lower()
    return round(difflib.SequenceMatcher(None, got, expected.lower()).ratio(), 3)


def evaluate_checkpoint(ckpt: Path, cfg: dict, ref: tuple[Path, str], asr_model) -> list[dict]:
    from f5_tts.api import F5TTS

    ecfg = cfg["evaluation"]
    out_dir = workspace_dir(cfg) / "eval" / ckpt.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    # use_ema=False per the f5_tts train README: for early finetune checkpoints
    # EMA weights are still dominated by the pretrained model.
    tts = F5TTS(model=cfg["exp_name"], ckpt_file=str(ckpt),
                use_ema=bool(ecfg.get("use_ema", False)))
    try:
        from voice_engine.metrics.similarity import SpeakerSimilarityMetric

        spk = SpeakerSimilarityMetric()
    except Exception:  # noqa: BLE001
        spk = None
    ref_audio, ref_text = ref
    rows = []
    for i, prompt in enumerate(ecfg["prompts"], 1):
        wav_path = out_dir / f"prompt{i}.wav"
        t0 = time.time()
        tts.infer(ref_file=str(ref_audio), ref_text=ref_text, gen_text=prompt,
                  file_wave=str(wav_path), nfe_step=ecfg["nfe_step"], seed=1234)
        infer_s = round(time.time() - t0, 2)
        import soundfile as sf

        data, sr = sf.read(wav_path)
        row = {
            "checkpoint": ckpt.name, "prompt": i,
            "audio_s": round(len(data) / sr, 2), "infer_s": infer_s,
            "rtf": round(infer_s / max(len(data) / sr, 1e-6), 2),
            "asr_similarity": asr_similarity(asr_model, wav_path, prompt),
        }
        if spk is not None:
            try:
                row["speaker_similarity"] = round(spk.compare(ref_audio, wav_path), 3)
            except Exception:  # noqa: BLE001 - optional backend (resemblyzer)
                pass
        rows.append(row)
        print(f"[evaluate] {ckpt.name} prompt{i}: {row}", flush=True)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate F5 fine-tune checkpoints")
    parser.add_argument("--watch", action="store_true", help="Poll for new checkpoints")
    parser.add_argument("--interval", type=int, default=120)
    args = parser.parse_args(argv)

    cfg = load_config()
    ckpt_dir = workspace_dir(cfg) / "ckpts" / cfg["dataset_name"]
    eval_dir = workspace_dir(cfg) / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    state_path = eval_dir / "evaluated.json"
    metrics_path = eval_dir / "metrics.csv"
    done = set(json.loads(state_path.read_text()) if state_path.exists() else [])

    ref = pick_reference(cfg)
    print(f"[evaluate] reference: {ref[0].name} — {ref[1][:60]}...")
    from faster_whisper import WhisperModel

    asr_model = WhisperModel("small", device="auto", compute_type="auto")

    while True:
        ckpts = sorted(p for p in ckpt_dir.glob("model_*.pt")) if ckpt_dir.is_dir() else []
        ckpts += sorted(ckpt_dir.glob("model_*.safetensors")) if ckpt_dir.is_dir() else []
        new = [c for c in ckpts if c.name not in done and c.name != "model_last.pt"]
        for ckpt in new:
            rows = evaluate_checkpoint(ckpt, cfg, ref, asr_model)
            write_header = not metrics_path.exists()
            with open(metrics_path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["checkpoint", "prompt", "audio_s",
                                                  "infer_s", "rtf", "asr_similarity",
                                                  "speaker_similarity"])
                if write_header:
                    w.writeheader()
                for r in rows:
                    w.writerow(r)
            done.add(ckpt.name)
            state_path.write_text(json.dumps(sorted(done), indent=1), encoding="utf-8")
        if not args.watch:
            if not new:
                print("[evaluate] no new checkpoints.")
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
