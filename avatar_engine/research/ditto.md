# Ditto — real-time streaming talking head

**Repo:** https://github.com/antgroup/ditto-talkinghead
**Verified:** 2026-07-04 · 826 stars · last push 2025-11-12 · slowing

## What it is

Ant Group's motion-space diffusion talking head (ACM MM 2025) engineered
for **real-time streaming**: audio chunks in, video frames out, with
TensorRT-compiled inference. The strongest open candidate for
*interactive* avatars (live Q&A hosts, voice-agent faces) as opposed to
rendered clips.

## License

Apache-2.0, code and weights.

## Hardware & install

~6 GB VRAM runtime, but the real cost is operational: TensorRT engines
must be built per GPU architecture/driver, making installs brittle and
CI-hostile. A slower PyTorch fallback exists. Linux-only in practice.

## Strengths / weaknesses

- + Real-time streaming generation; stable identity (motion-space
  approach); commercial-clean license.
- + Inpaints only the face region — background/torso pixel-static
  (predictable, but also a look).
- − No hand/torso motion at all; small community; TensorRT fragility.

## Role

The interactive-avatar track candidate. Benchmark offline first; invest in
TensorRT packaging only if the interactive product line is greenlit.

## Sources

- https://github.com/antgroup/ditto-talkinghead
- SoulX-LiveTalk technical report (arXiv:2512.23379) — independent
  comparison confirming Ditto's static-torso limitation
