# Reference audio for voice cloning benchmarks

Place cleaned reference clips here (gitignored except this README).

## Synthetic clips (Phase A1.5)

`synthetic/` holds machine-generated reference clips (Kokoro af_heart EN /
hf_alpha HI voices) produced by
`python -m voice_engine.scripts.generate_reference_clips` in 10/20/30/60 s
variants. They exercise reference *acceptance mechanics* and give the
speaker-similarity metric a real target, but they are **not** substitutes
for human-recorded references: cloning-quality listening tests still
require the human set below.

## Required set (record once, reuse across all engines)

| File | Speaker | Language | Duration | Notes |
| --- | --- | --- | --- | --- |
| `male_en_20s.wav` | Adult male | English (Indian accent) | 20 s | Neutral narration |
| `female_en_20s.wav` | Adult female | English (Indian accent) | 20 s | Neutral narration |
| `male_hi_20s.wav` | Adult male | Hindi | 20 s | Conversational |
| `female_hi_20s.wav` | Adult female | Hindi | 20 s | Conversational |
| `female_bn_20s.wav` | Adult female | Bengali | 20 s | Conversational |
| `male_en_6s.wav` | Adult male | English | 6 s | Short-reference condition |

## Recording standards

- 16-bit PCM WAV, mono, 24 kHz or higher (engines resample internally).
- Quiet room, no reverb, no background music, mic 15-30 cm from mouth.
- Natural speech (read a paragraph, not isolated words); no clipping.
- Each clip must have a matching transcript in `transcripts.yaml`
  (`filename -> exact text`) — several engines (F5-TTS, Dia, CosyVoice)
  require the reference transcript for prompt conditioning.
- Obtain written consent from every speaker; store consent reference in
  `voice_engine/voices/` metadata when profiles are created (Phase A2).

`BaseVoiceAdapter.validate_reference()` enforces duration/clipping/silence
rules programmatically — run `python -m voice_engine.scripts.validate_references`
after adding files.
