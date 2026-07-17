"""Phase T3 — F5-TTS production fine-tuning pipeline.

One command prepares everything and (only when explicitly asked) launches
training:

    python -m production.f5_finetune.run             # prep + dry-run plan
    python -m production.f5_finetune.run --start     # prep + launch training

Stages (each reuses existing infrastructure; see TRAINING_PLAN.md):
  1. transcribe  - faster-whisper over the ACCEPTED production segments
                   (read-only on the dataset) -> workspace metadata.csv
  2. prepare     - charset check vs the pretrained vocab, then the f5_tts
                   packaged prepare_csv_wavs (--finetune mode) -> raw.arrow
  3. launch      - accelerate + f5_tts.train.finetune_cli with the committed
                   config (checkpoints, resume, fp16, tensorboard, samples)
  4. evaluate    - per-checkpoint objective eval (voice_engine.metrics)

All stages run inside the f5-tts model venv (same dispatch pattern as
voice_engine/scripts/setup_benchmark.py).
"""
