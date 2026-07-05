# EchoMimic family (Ant Group) — audio-driven portrait & body animation

All three generations are **Apache-2.0** (code + weights), actively
maintained by Ant Group. Verified 2026-07-04.

## EchoMimic v1 (AAAI 2025)

4,261 stars · last push 2026-04-07. Audio-driven portrait animation with
editable landmark conditioning. Superseded by v2/v3 for our purposes;
kept for reference only.

## EchoMimic v2 (CVPR 2025) — `echomimic-v2`

4,607 stars · last push 2026-02-23 · active.

- **Half-body** animation with hand gestures from image + audio —
  meaningfully richer than head-only output for presenter-style content.
- Hardware: community reports 8 GB cards hang; **16 GB practical floor**,
  24 GB comfortable. Minutes per clip (offline).
- Official English + Mandarin driving audio support.

## EchoMimic v3 (AAAI 2026) — `echomimic-v3`

968 stars · last push 2026-03-18 · active, newest of the family.

- **1.3B params, unified multi-modal/multi-task** (talking head + talking
  body in one model).
- Hardware (flash variant, 8 steps): **768×512 in 6.5 GB, 768×768 in
  12 GB** — the best quality-per-GB envelope of any audio-driven candidate.
- Young project; community still small; fewer deployment war stories.

## Platform take

v3 is the **primary production candidate** for image→talking-avatar
generation: Apache-2.0, active, hardware-affordable, current-generation
quality. v2 stays on the benchmark roster as the gesture-rich fallback
where its VRAM cost is acceptable.

## Sources

- https://github.com/antgroup/echomimic_v3 (12G/6.5G VRAM claims in README)
- https://github.com/antgroup/echomimic_v2
- https://github.com/antgroup/echomimic (Apache-2.0 LICENSE)
