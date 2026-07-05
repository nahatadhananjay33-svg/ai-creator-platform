# Dia (Nari Labs)

**Verdict: a specialist, not a generalist — unmatched for short expressive
English dialogue clips (podcast-style, non-verbals), unsuitable for
narration, Indic languages, or real-time. Keep as a creative tool for
English dialogue content.**

## Architecture

- 1.6B-parameter encoder-decoder over audio codec tokens, generating full
  multi-speaker dialogues in one pass from `[S1]`/`[S2]`-tagged scripts.
- Produces non-verbal events from text tags: `(laughs)`, `(coughs)`,
  `(clears throat)` — genuinely rare capability.

## License and commercial usage

Apache-2.0 code and weights. Commercial use permitted.

## Repository and community

- github.com/nari-labs/dia — viral 2025 release (two-person team), large
  star count but small maintainer base; release cadence slowed after launch.
  Bus-factor risk for production reliance.

## Voice cloning

- Audio-prompt continuation: prepend reference audio + its transcript; the
  model continues in that voice.
- Consistency is per-generation — without a fixed seed/prompt the voice
  changes run to run. Speaker identity control is the weakest of the
  candidates.

## Languages

English only. No Hindi/Hinglish/Bengali, no roadmap for them.

## Performance (research figures)

- ~10 GB VRAM full precision, ~5-6 GB bf16; roughly real-time-ish generation
  on datacenter GPUs, slower on consumer cards.
- Known issues: pacing drifts on long scripts (speeds up), occasional
  runaway generations — our `duration_ratio_vs_expected` metric exists
  largely for models like this.

## Streaming

**NOT SUITABLE.** Whole-utterance generation, high latency.

## Use-case fit

| Use case | Fit |
| --- | --- |
| Two-speaker skit/podcast Reels (EN) | Excellent — nothing else open does this |
| Narration / audiobooks | Poor (pacing instability) |
| Voice AI | Not suitable |
| Indic content | Not possible |

## Strengths / weaknesses

**+** Dialogue realism + non-verbals; Apache-2.0; distinctive creative niche.
**−** English only; unstable speaker identity; VRAM-hungry; small team;
no streaming; long-form unreliable.
