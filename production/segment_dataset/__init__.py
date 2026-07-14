"""Phase V4 — Intelligent Production Voice Dataset Builder.

Additive upgrade over ``production.voice_dataset``: instead of accepting or
rejecting whole recordings, every recording is segmented into 5-20 s speech
segments via energy VAD and each segment is evaluated independently, so the
excellent speech inside an imperfect recording is no longer wasted.

Policy changes vs the whole-file builder (documented, deterministic):
- Speaker: recordings are assumed to be one creator; a segment is rejected
  only on HIGH-confidence overlap (wide f0 spread inside a short segment),
  never on natural pitch variation across a long take.
- Background noise: steady ambience never auto-rejects; a segment is rejected
  only when noise actually masks the speech (low segment SNR).

Reuses the existing builder's analysis, scoring, extraction, and config bands
without modifying them. No training.
"""
