# Emerging / Additional Models (2025-2026 scan)

Newer production-relevant open models beyond the original candidate list.
Adapters exist where noted; others are documented for A2 re-evaluation.

## Kokoro-82M (hexgrad) — adapter: `kokoro`

**Primary candidate, real-time CPU tier.** StyleTTS2-derived, 82M params,
Apache-2.0. Curated voice packs — **including Hindi voices (hf_alpha,
hf_beta, hm_omega, hm_psi)** — plus EN/JA/ZH/ES/FR/IT/PT. CPU real-time
(RTF < 0.5 on laptop cores), tiny footprint (~350 MB), widely deployed in
real-time agent stacks and edge apps. No cloning, no emotion control.
The pragmatic answer for phone-agent TTS where a *branded* (not cloned)
voice is acceptable and GPUs are scarce.

## Orpheus (Canopy Labs)

Llama-3B backbone over SNAC codec tokens; Apache-2.0; English (+research
multilingual drops incl. Hindi family experiments); designed for
**streaming** (~200 ms class latency with realtime decode) and emotive tags
(`<laugh>`, `<sigh>`); zero-shot cloning. Heavier than Kokoro but genuinely
conversational. Evaluate for the real-time tier in A2 alongside CosyVoice.

## Zonos-v0.1 (Zyphra)

1.6B transformer/SSM hybrids; Apache-2.0; zero-shot cloning from 5-30 s;
EN/JA/ZH/FR/DE; 44.1 kHz output, emotion vector control. Quality strong,
ecosystem younger. No Indic languages. Watch.

## GPT-SoVITS

MIT; few-shot cloning king for ZH/JA/KO/EN with 1-minute fine-tunes; huge
hobbyist community. No Hindi/Bengali; production serving story weak
(research-grade codebase). Not for us.

## IndexTTS-2 (Bilibili)

Industrial-grade zero-shot TTS with **duration-controllable** generation
(critical for dubbing/lip-sync — relevant to Phase A4 talking avatars) and
emotion-timbre disentanglement. Code Apache-2.0; **weights under a
restricted non-commercial-ish license — verify before any use.** ZH/EN.
Track for avatar dubbing use case.

## Higgs Audio V2 (Boson AI)

3B (Llama-3.2 base) unified audio-language model; strong expressive
multi-speaker generation; permissive positioning (verify current terms).
EN-centric with multilingual claims. Heavy. Watch.

## VibeVoice (Microsoft)

Long-form multi-speaker (up to ~90 min, 4 speakers) — podcast generator
class; MIT release, but Microsoft **pulled/re-scoped the repo** shortly
after launch over misuse concerns; treat availability as unstable.
EN/ZH. Not a platform dependency.

## Fish Speech / OpenAudio S1-mini

High-quality multilingual (incl. some Indic coverage claims); weights
**CC-BY-NC** — non-commercial. API is the commercial path. Excluded.

## NeuTTS Air (Neuphonic)

0.5B on-device TTS (GGML), instant cloning from ~3 s, runs on
phones/Raspberry Pi. Apache-2.0. English-first. Relevant future edge story
(WhatsApp voice generation on low-cost infra). Watch.

---

### Scan conclusion

The 2025 generation splits cleanly into (a) **LLM-token quality engines**
(Chatterbox, Orpheus, Higgs, IndexTTS-2) and (b) **small real-time engines**
(Kokoro, NeuTTS) — with CosyVoice 2 almost alone in doing quality *and*
low-latency streaming, and AI4Bharat models almost alone on Indic depth.
No single open model covers quality + streaming + Hindi + Bengali +
commercial license. That fact drives the dual-tier recommendation in
[docs/PHASE_A1_FINAL_REPORT.md](../../docs/PHASE_A1_FINAL_REPORT.md).
