# SadTalker — legacy talking-head baseline

**Repo:** https://github.com/OpenTalker/SadTalker
**Verified:** 2026-07-04 · 13,937 stars · last push 2024-06-26 · **stale**

## What it is

CVPR 2023 image→talking-head via learned 3D motion coefficients. For two
years the default open talking-head tool; now clearly behind diffusion
models on realism, but still the easiest full pipeline to stand up and the
lowest hardware bar of any audio-driven candidate.

## License

Relicensed to **Apache-2.0**; the earlier "non-commercial" README wording
was retracted (issues #583, #293 record the confusion; the LICENSE file
governs). Third-party components keep their own licenses — check GFPGAN
weights if the enhancer is enabled.

## Hardware

4 GB VRAM comfortable; CPU-only inference works (minutes per second of
video) — the only candidate that runs at all on this Windows/CPU dev
machine, which makes it the designated **first real adapter** for pipeline
validation in early Phase A4.

## Strengths / weaknesses

- + Trivial install; tiny hardware; permissive license; huge install base.
- − Unmaintained since mid-2024; stiff neck motion, waxy skin, jaw
  artifacts; quality gap vs 2024+ models grows every quarter.

## Role

Low-end fallback and the benchmark's quality floor: any candidate that
cannot clearly beat SadTalker on the human rubric is disqualified.

## Sources

- https://github.com/OpenTalker/SadTalker (+ LICENSE)
- https://github.com/OpenTalker/SadTalker/issues/583
