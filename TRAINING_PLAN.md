# F5-TTS Fine-Tuning Plan — Phase T3

Generated: 2026-07-17
One command: `python -m production.f5_finetune.run --start` (Colab T4) · one notebook cell: cell 7 of
[tanshi_voice_cloning_setup.ipynb](notebooks/tanshi_voice_cloning_setup.ipynb) with `START_TRAINING = True`.
Without `--start` / with `START_TRAINING = False` everything is prepared and the exact training
command is printed, but **no training begins** (T3 requirement).

## What trains

- Base: `F5TTS_v1_Base` (336 M param DiT, flow matching), pretrained weights auto-downloaded from
  `SWivid/F5-TTS` (already in the HF cache from T1/T2).
- Data: the **production dataset** — 550 accepted segments, 1.327 h audio (1.108 h speech),
  single speaker, avg SNR ≈ 30 dB. The dataset is read-only for this phase; transcripts and all
  derived artifacts live in a separate workspace.
- Objective: speaker adaptation (voice cloning quality for Tanshi's voice), not language modeling.

## Pipeline stages (all reused infrastructure, see AUDIT trail in F5_FINETUNE_REPORT.md)

| Stage | Command (auto-sequenced by `run.py`) | What it does |
| --- | --- | --- |
| 1. Transcribe | `production.f5_finetune.transcribe` (in f5 venv) | faster-whisper `large-v3` over accepted segments → `metadata.csv` (`audio_file\|text`). Hindi is romanized (ITRANS, lowercased) because the pretrained vocab is Emilia ZH/EN — Devanagari is not in it. Degenerate/no-speech transcripts dropped and reported. |
| 2. Prepare | `production.f5_finetune.prepare` (in f5 venv) | Hard charset check of every transcript against the actual pretrained vocab (fails loudly, per-file report), then the **packaged** `prepare_csv_wavs.py` in fine-tune mode → `raw.arrow` + `duration.json` + pretrained `vocab.txt`. 48 kHz segments are resampled to 24 kHz on the fly by F5's dataset loader — no audio copies are made. |
| 3. Train | `accelerate launch … f5_tts.train.finetune_cli` | The **packaged** trainer with our config (below). Checkpoints, resume, fp16, tensorboard and per-checkpoint sample audio are all built into it — zero training code written. |
| 4. Evaluate | `production.f5_finetune.evaluate --watch` | Sidecar process: every new checkpoint → synthesizes 3 fixed eval prompts (never in training data) with the highest-SNR reference → `metrics.csv` (audio duration, RTF, ASR round-trip similarity, speaker similarity when resemblyzer present) + sample WAVs per checkpoint. Idempotent via `evaluated.json`. |

## Checkpoints, resume, persistence

- Trainer saves `model_<updates>.pt` every **500 updates** (keep last 6) and refreshes
  `model_last.pt` every **250 updates**.
- `ckpts/<dataset>` is **symlinked into the Drive workspace** on Colab, so a runtime disconnect
  loses at most 250 updates. Re-running the same cell auto-resumes from `model_last.pt`.
- Additionally `--log_samples` makes the trainer itself write reference/generated WAVs at every
  checkpoint save — sample audio from every checkpoint comes from two independent paths.

## Budget arithmetic (T4, fp16)

- ~4 777 s audio × 93.75 mel fps ≈ **448 k frames/epoch**; effective batch 3200 × 2 (accum)
  = 6 400 frames → **~70 updates/epoch**; 50 epochs ≈ **3 500 updates**.
- Checkpoints: ~every 7 epochs → ~7 evaluated checkpoints.
- Expected T4 wall time ≈ 6–10 h total. Free Colab sessions are shorter than that — the
  resume design assumes **2–3 sessions**; nothing is lost between them.

## Success criteria & risks

- Pick the winning checkpoint from `eval/metrics.csv` (speaker-similarity ↑, ASR-similarity ≥
  base model, no degradation over updates → watch for overfitting after ~30 epochs) plus
  listening to the per-checkpoint samples.
- **Risk — romanized Hindi:** the base model never saw romanized Hindi; intelligibility must be
  judged from the checkpoint samples early (first checkpoint ≈ 45 min in). Fallback documented in
  F5_FINETUNE_REPORT.md (IndicF5 base or vocab extension).
- **Risk — 1.1 h of data:** small for TTS fine-tuning; mitigations already in config: low LR
  (1e-5), EMA disabled for evaluation of early checkpoints, frequent checkpoints to catch the
  quality peak before overfit.
- License: base weights are CC-BY-NC-4.0; fine-tuned weights inherit this. Fine for internal
  R&D; commercial deployment needs the relicensing path already flagged in F5_SETUP_REPORT.md.
