# F5-TTS Fine-Tuning Readiness Report — Phase T3

Generated: 2026-07-17
Verdict: **repository is one command away from starting fine-tuning** —
`python -m production.f5_finetune.run --start` on Colab T4, or notebook cell 7 with
`START_TRAINING = True`. Training was **not** started (T3 requirement). The production dataset
was not modified (all stages read it read-only; derived artifacts live in a separate workspace).

## 1. Audit: what was reused (nothing re-implemented)

| Need | Reused | Where |
| --- | --- | --- |
| Trainer (checkpoints, resume, fp16, tensorboard, per-ckpt samples) | `f5_tts.train.finetune_cli` via `accelerate` — shipped in the already-installed f5-tts venv | stage 3 |
| Dataset builder (arrow + durations + pretrained vocab) | `f5_tts/train/datasets/prepare_csv_wavs.py` (fine-tune mode) | stage 2 |
| Venv dispatch pattern | same as `voice_engine/scripts/setup_benchmark.py` (T1/T2), incl. the MPLBACKEND=Agg lesson | all stages |
| Environment/venv resolution | `foundation.model_manager.installer.model_venv_python` | `common.py` |
| Objective metrics | `voice_engine.metrics.SpeakerSimilarityMetric` (graceful skip), soundfile stats | stage 4 |
| Dataset trust | `production/cloud_setup` manifest already validates the Drive copy in notebook cell 5 | prerequisite |

New code is confined to [production/f5_finetune/](production/f5_finetune/) (~5 small scripts + config).

## 2. Dataset compatibility — verified, with one required transform

- 550 accepted segments / 1.327 h (manifest-verified); 48 kHz mono WAV — F5's loader resamples
  to 24 kHz on the fly, no re-encoding needed. Durations (avg ≈ 8.7 s) sit in F5's sweet spot.
- **Gap found: no transcripts.** F5 fine-tuning needs `audio_file|text`. Stage 1 generates them
  with faster-whisper (`large-v3` on T4) — read-only on the dataset.
- **Language verified by sample run (3 segments, local):** code-switched **Hinglish**. English
  spans transcribe cleanly. Devanagari output is romanized (ITRANS, lowercased) because the
  pretrained vocab is Emilia ZH/EN; `prepare` hard-fails if any character remains uncovered.
- Sample run caveats (both already fixed in code):
  - whisper-`small` on CPU (debug config) produced poor Hindi + repetition loops — production
    config uses `large-v3` + `condition_on_previous_text=False`; inspect
    `transcripts/transcribe_report.json` before training.
  - Devanagari danda (।) transliterated to `|`, the manifest delimiter — now sanitized.

## 3. Training configuration (details in TRAINING_CONFIG.md)

Dataset path, checkpoint dir, output/workspace dirs, tensorboard logging, fp16, resume — all in
[production/f5_finetune/config.yaml](production/f5_finetune/config.yaml), environment-aware
(local vs Colab). Checkpoints persist to Drive via symlink; auto-resume from `model_last.pt`
after any disconnect.

## 4. Checkpoint saving, evaluation, sample audio

- Automatic checkpoints: every 500 updates (+ `model_last.pt` every 250, keep last 6).
- Automatic evaluation per checkpoint: `evaluate.py --watch` sidecar — 3 fixed prompts,
  ASR round-trip similarity, RTF, speaker similarity (when resemblyzer present), CSV + JSON state.
- Sample audio per checkpoint from **two** paths: the trainer's own `--log_samples`, and the
  evaluator's prompt WAVs under `<workspace>/eval/<checkpoint>/`.
- All training logs stream to `<workspace>/logs/` and tensorboard `runs/` (Drive-persisted).

## 5. Verified locally (CPU box, no training possible here)

- All module files compile; stage guards fire correctly (`launch` refuses to run without the
  prepared arrow; `run` refuses without the venv).
- Stage 1 executed end-to-end on 3 real segments: transcripts + `metadata.csv` +
  report produced in the workspace.
- The full transcribe→prepare→dry-run path is what notebook cell 7 executes with
  `START_TRAINING = False` — run that once on Colab as the final pre-flight.

## 6. Open risks (decide with first-checkpoint evidence, ~45 min into training)

1. **Romanized Hindi intelligibility** — base model never saw romanized Hindi. If the first
   checkpoint's samples are poor on Hindi prompts while English is fine, fall back to
   **IndicF5 (AI4Bharat)** as the base (native Hindi, own license terms) or extend the vocab
   (needs more data; not recommended at 1.1 h).
2. **Transcript quality ceiling** — large-v3 will be far better than the sample, but review
   `transcribe_report.json` (drop counts, language mix) before `--start`.
3. **License** — fine-tuned weights inherit CC-BY-NC-4.0 from the base (flagged since T1).
