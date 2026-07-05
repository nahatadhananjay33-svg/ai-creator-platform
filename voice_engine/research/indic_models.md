# Indic Specialists: Indic Parler-TTS and IndicF5

Our platform's hardest requirement — production Hindi, Hinglish, and
Bengali — is best served by models built *for* Indian languages. Two
AI4Bharat (IIT Madras) lineages matter.

## Indic Parler-TTS (AI4Bharat × Hugging Face)

**Verdict: the only commercially-clean model with first-class Hindi AND
Bengali today. Primary candidate for Indic content voices; not a cloning
model.**

- **Architecture:** Parler-TTS (~880M): decoder-only transformer conditioned
  on a natural-language *voice description*; trained on ~10k+ hours across
  20 Indic languages + English.
- **License:** Apache-2.0 code and weights. Commercial OK.
- **Languages:** HI and BN native (plus TA/TE/KN/ML/MR/GU/PA/OR/AS/UR and
  more). Handles code-mixed input reasonably (training corpora include
  code-mixed speech) — verify Hinglish with raters.
- **Voices:** 69 recurring named speakers (e.g. Rohit, Divya, Aditi,
  Sita); a named speaker + fixed description gives a *reproducible branded
  voice* — exactly what a real-estate agent persona needs. What it cannot
  do is clone a specific real person from audio.
- **Emotion/style:** via description text ("speaks slowly with empathy") —
  10 languages have official expressivity support.
- **Hardware:** ~6-8 GB VRAM comfortable; GPU RTF < 1; CPU too slow for
  real-time. No native streaming (LIMITED) — sentence pipelining required.
- **Risks:** generation length caps favor sentence-wise synthesis; number/
  acronym normalization for Indic scripts needs our pronunciation layer
  (RERA numbers, phone numbers — see `voice_engine/pronunciation/`).

## IndicF5 (AI4Bharat)

**Verdict: the zero-shot *cloning* complement — F5-TTS architecture trained
on 11 Indian languages. License must be verified before commercial use.**

- **Architecture:** F5-TTS (flow-matching DiT) polyglot checkpoint trained
  on ~1417 hours (IndicTTS/IndicVoices-R and related corpora); zero-shot
  cloning with 5-10 s reference + transcript, same as base F5.
- **Languages:** Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada,
  Malayalam, Punjabi, Odia, Assamese.
- **License:** repo/model-card terms have carried research-oriented wording;
  **treat commercial use as unverified** — confirm with AI4Bharat before
  deployment (they have historically been permissive with attribution, and
  several of their corpora are CC-BY-4.0, but the checkpoint terms govern).
- **Quality expectation:** the best open Hindi/Bengali *cloning* quality
  available; Hinglish via mixed-script text is plausible but unproven —
  a core A2 listening-test question.
- **No adapter yet:** runs through the F5-TTS adapter with
  `model_name`/checkpoint override once weights are fetched; formal adapter
  subclass (`indicf5`) is an A2 task alongside license confirmation.

## Why these two together matter

Indic Parler-TTS (branded persona voices, clean license) + IndicF5 (true
cloning) cover the Indic axis that every general-purpose candidate misses:
Chatterbox has Hindi but no Bengali; CosyVoice/F5-base/StyleTTS have neither;
XTTS has Hindi but a dead-end license. Any final architecture that takes
Hindi/Hinglish/Bengali seriously builds on at least one of these.
