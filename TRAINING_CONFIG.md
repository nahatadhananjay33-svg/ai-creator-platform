# F5-TTS Training Configuration — Phase T3

Single source of truth: [production/f5_finetune/config.yaml](production/f5_finetune/config.yaml).
This document explains every knob; change values in the YAML, never in code.

## Identity

| Key | Value | Why |
| --- | --- | --- |
| `exp_name` | `F5TTS_v1_Base` | Pretrained experiment; weights auto-resolve from `SWivid/F5-TTS` (HF cache). |
| `dataset_name` | `tanshi_voice` | Names both `data/tanshi_voice_pinyin/` (arrow) and `ckpts/tanshi_voice/`. |
| `model` | `f5-tts` | voice_engine adapter/venv id — every stage runs in `.venvs/f5-tts`. |

## Paths (auto-selected by environment)

| Env | Dataset (read-only) | Workspace (transcripts, ckpts, logs, eval) |
| --- | --- | --- |
| local | `D:/AI_CREATOR_DATA/Tanshi/production_voice_dataset` | `D:/AI_CREATOR_DATA/Tanshi/f5_finetune_workspace` |
| colab | `…/MyDrive/Ai_creator/Voice_AI_Tanshi/production_voice_dataset` | `…/MyDrive/Ai_creator/Voice_AI_Tanshi/f5_finetune` |

The arrow dataset intentionally stays on the runtime's local disk (fast, rebuildable in ~1 min);
checkpoints/logs/eval go to the workspace (Drive on Colab) for persistence.

## Transcription

| Key | Value | Why |
| --- | --- | --- |
| `whisper_model` | `large-v3` | Best Hindi accuracy; fits T4 (float16). Local CPU probes use `small`. |
| `language` | `hi` | Decode bias; code-switched English still comes through. |
| `romanize` | `true` | Pretrained vocab is Emilia ZH/EN — Devanagari must become Latin (ITRANS, lowercased). `prepare` hard-fails if any char is still uncovered. |
| `min_chars` / `max_no_speech_prob` | 4 / 0.5 | Drops degenerate transcripts and segments Whisper flags as non-speech; all drops are logged, none touch the dataset. |

## Training (maps 1:1 to `finetune_cli` flags)

| Key | Value | Why |
| --- | --- | --- |
| `learning_rate` | `1e-5` | Conservative speaker-adaptation LR for 1.1 h of data (finetune_cli default). |
| `batch_size_per_gpu` | `3200` frames | ≈ 34 s of mel per step; safe for T4 16 GB at fp16. Raise to 4800 if VRAM headroom shows. |
| `grad_accumulation_steps` | `2` | Effective 6 400 frames/update without extra VRAM. |
| `epochs` | `50` | ≈ 3 500 updates; the eval curve decides the actual stopping checkpoint. |
| `num_warmup_updates` | `400` | ~11 % warmup. |
| `save_per_updates` | `500` | Checkpoint ≈ every 7 epochs → ~7 evaluated checkpoints. |
| `keep_last_n_checkpoints` | `6` | Bounds Drive usage (~1.35 GB per checkpoint). |
| `last_per_updates` | `250` | `model_last.pt` refresh = resume granularity after a disconnect. |
| `mixed_precision` | `fp16` | T4 has no bf16; passed to `accelerate launch`. |
| `tokenizer` | `pinyin` | Fine-tune keeps the pretrained Emilia vocab (materialized by `prepare`). |
| `logger` | `tensorboard` | Local logs, no wandb account needed; `runs/` lands in the ckpts dir (Drive). |
| `log_samples` | `true` | Trainer writes ref/gen WAVs at every checkpoint save. |

## Evaluation (sidecar, per checkpoint)

| Key | Value | Why |
| --- | --- | --- |
| `prompts` | 3 fixed EN/Hinglish lines | Never in the training data; comparable across checkpoints. |
| `reference` | `auto` | Highest-SNR accepted segment + its stage-1 transcript. |
| `nfe_step` | 32 | Default inference quality/speed tradeoff. |
| `use_ema` | `false` | f5 README: EMA weights of early fine-tune checkpoints are still dominated by the pretrained model. |
| `install_optional_backends` | `false` | Speaker-similarity uses resemblyzer only if present (won't build on Windows); ASR-similarity and audio stats always run. |

## Resume behavior

Re-running the same command auto-resumes: the packaged trainer loads
`ckpts/tanshi_voice/model_last.pt` when it exists. Fresh start = delete/rename the workspace
`ckpts/tanshi_voice/` directory. `--pretrain <path>` can substitute a different starting
checkpoint without config changes.
