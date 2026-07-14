"""Phase V2 — Long-form Voice Dataset Validation.

Evaluates whether the creator's long-form YouTube videos are suitable for
production voice cloning. Pure orchestration: downloads long-form videos with
the existing Media Acquisition engine, builds the dataset with the existing
Voice Dataset Builder (via the V1 voice_pipeline glue), then reports
statistics, a random inspection, a comparison against the raw-video baseline
dataset, and a final A/B/C recommendation. No training, no threshold changes,
no modifications to the reused modules.
"""
