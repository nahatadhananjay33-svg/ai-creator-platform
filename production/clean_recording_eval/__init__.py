"""Phase V3 — Clean Recording Quality Evaluation.

Evaluates a new clean microphone recording as a standalone voice-cloning
dataset. Pure orchestration: safe ingest from Downloads (no overwrite, sha256
verified), the existing Voice Dataset Builder via the V1 glue (unchanged
thresholds), statistics/inspection reused from Phase V2, plus a deterministic
Voice Cloning Readiness Score and a final A/B/C recommendation. No training,
no modifications to the reused modules.
"""
