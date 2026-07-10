# AI Creator Platform — Version 1.0

Turn one line of text into an upload-ready social reel with a single command:

```bash
python -m creator.run --prompt "5 tips for first-time home buyers"
```

That one command runs the whole pipeline end to end and leaves you with a
finished reel **and** the captions/hashtags to post it:

```
Prompt  →  Workflow  →  Quality  →  Upload Metadata  →  Finished
```

Version 1.0 is deliberately **single-user and local**: it runs in **VS Code** or
**Google Colab**, needs no cloud, no accounts, and no API keys. It never posts
anything anywhere — it writes files you copy into each platform yourself.

- **Instagram Reels / YouTube Shorts / TikTok** vertical videos
- **Square** feed posts and **landscape** YouTube renditions
- Deterministic, hermetic **`mock` renderer** (no GPU/FFmpeg) for trying it out,
  plus a real **`ffmpeg` renderer** for shareable MP4s
- Upload-ready **titles, descriptions, captions, and hashtags** per platform

---

## Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Generate your first reel](#generate-your-first-reel)
5. [Configuration](#configuration)
6. [The workflow](#the-workflow)
7. [Troubleshooting](#troubleshooting)
8. [Project layout](#project-layout)
9. [Documentation](#documentation)
10. [Scope](#scope)

---

## Requirements

- **Python ≥ 3.10**
- The core install has **no heavy ML dependencies** — it installs and runs
  without a GPU or any model weights.
- **FFmpeg** is optional. You only need it for the real-video `--renderer ffmpeg`
  path; the default `mock` renderer needs nothing extra.

---

## Installation

### VS Code / local

```bash
# from the repo root
python -m venv .venv
source .venv/bin/activate        # Windows Git Bash: source .venv/Scripts/activate
pip install -e .[dev]            # core only — no GPU, no model weights

pytest                           # optional: verify the suite is green
```

### Google Colab

```python
!git clone https://github.com/<your-username>/ai-creator-platform.git
%cd ai-creator-platform
!pip install -e .[dev]

!python -m creator.run --prompt "Why compounding is a superpower" --template finance
```

Colab storage is ephemeral — the generated `workspace/` is git-ignored and will
not persist between sessions. Download anything you want to keep.

---

## Quick Start

```bash
# 1) Generate a reel with the built-in defaults (hermetic mock renderer)
python -m creator.run

# 2) Your own idea + content vertical
python -m creator.run --prompt "3 mistakes new investors make" --template finance

# 3) Real MP4s instead of the mock proxy (needs FFmpeg installed)
python -m creator.run --renderer ffmpeg

# 4) See all options
python -m creator.run --help
```

Every run prints its four steps and finishes with the title, hashtags, and the
folder that holds everything you need to upload:

```
[1/4] Workflow  — generating the reel …
[2/4] Quality   — checking the reel …        PASS
[3/4] Upload    — writing upload-ready metadata …
[4/4] Finished

Title    : 3 mistakes new investors make
Hashtags : #investing #finance #money …
Exports  : workspace/exports/3-mistakes-new-investors-make

=== DONE (mock) — your reel is ready to upload ===
```

---

## Generate your first reel

1. Run the command:

   ```bash
   python -m creator.run --prompt "Why investing in real estate early is beneficial" \
       --template real_estate
   ```

2. Everything lands in one standardized **workspace** (created automatically):

   ```
   workspace/
     projects/   the full run for each reel (storyboard → voice → render)
     exports/    ← your finished, upload-ready bundle lives here
     cache/      reusable intermediate artifacts (safe to delete)
     assets/  voices/  avatars/  music/     your input material
     logs/       per-run logs
   ```

3. Open **`workspace/exports/<your-prompt-slug>/`**. It contains:

   | File | What it is |
   | --- | --- |
   | `master__reel_9x16.*` | the vertical Reels/Shorts/TikTok rendition |
   | `master__square_1x1.*` | the square feed rendition |
   | `metadata.json` | machine-readable titles / captions / hashtags |
   | `upload_preview.md` | copy-paste-ready text for each platform |

4. Open `upload_preview.md`, copy the caption for your platform, upload the
   matching video, and you're done.

---

## Configuration

Everything a single user touches lives in **one documented file**,
[`creator/config.yaml`](creator/config.yaml). Every option has a safe default;
change only what you need.

| Section | Option | Meaning |
| --- | --- | --- |
| `generation` | `prompt` | the idea for your reel |
| | `template` | content vertical: `general`, `real_estate`, `finance`, `education`, `medical`, `news`, `motivational`, `talking_head` |
| | `renderer` | `mock` (fast, no deps) or `ffmpeg` (real MP4s) |
| | `profiles` | aspect ratios: `reel_9x16`, `square_1x1`, `landscape_16x9` |
| | `language` | narration/caption language (`en`, `hi`, …) |
| `branding` | `creator`, `channel` | your name/handle, shown in captions + metadata |
| `quality` | `gate` | refuse to write metadata unless the reel passes the quality check |
| `paths` | `root` | workspace location (empty → `<repo>/workspace`) |

**Four ways to set any option, lowest priority to highest:**

1. the defaults in `creator/config.yaml`
2. a config file you pass with `--config my_channel.yaml`
3. an environment variable, e.g. `AICP__generation__renderer=ffmpeg`
4. an explicit CLI flag, e.g. `--renderer ffmpeg`

```bash
# save your channel's settings once, reuse them everywhere
python -m creator.run --config my_channel.yaml
```

> The per-engine `defaults.yaml` files (script, voice, captions, branding,
> music, …) remain the advanced layer beneath this; a Version 1.0 user never
> needs to touch them.

---

## The workflow

`python -m creator.run` composes four existing subsystems — it adds no new
generation logic of its own:

| Step | Engine | What happens |
| --- | --- | --- |
| **Prompt → Workflow** | Workflow Engine | builds the reel through a deterministic 10-stage DAG: storyboard → scene plan → voice → avatar → assets → media intelligence → editing → timeline → render → export |
| **Quality** | Quality Engine | deterministic PASS/FAIL checks (video present, duration, aspect, audio, captions, exports). With `quality.gate` on, a FAIL stops here |
| **Upload Metadata** | Upload Assistant | writes `metadata.json` + `upload_preview.md` from the reel's storyboard |
| **Finished** | — | copies the finished renditions next to their metadata in `workspace/exports/` |

**Renderers.** `mock` produces a deterministic, dependency-free proxy video
(great for trying the platform and for tests). `ffmpeg` produces real `.mp4`
files and requires FFmpeg on your PATH.

**Determinism.** The same prompt reuses the same `projects/<slug>` run folder, so
re-runs are content-addressed and reproducible.

---

## Troubleshooting

The command fails fast with a plain `Error:`/`Hint:` for common mistakes — no
stack traces.

| Message | Fix |
| --- | --- |
| `No prompt to generate from.` | pass `--prompt "your idea"` or set `generation.prompt` in the config |
| `Unknown template: '…'` | use one of the listed templates (e.g. `real_estate`, `finance`) |
| `Unknown export profile(s): …` | use `reel_9x16`, `square_1x1`, and/or `landscape_16x9` |
| `The 'ffmpeg' renderer needs FFmpeg …` | install FFmpeg, or use `--renderer mock` |
| `Config file not found: …` | check the `--config` path, or omit it to use defaults |
| `the reel did not pass the quality check` | adjust the prompt/template, or pass `--no-quality-gate` to write metadata anyway |

Re-run with `--verbose` to see the detailed engine logs for anything unexpected.

---

## Project layout

The platform is a set of independent **engines** on a shared **foundation**;
`creator/` is the Version 1.0 usability layer that ties them together.

| Path | Purpose |
| --- | --- |
| `creator/` | **Version 1.0 front door**: the single `run` command, workspace, and config |
| `foundation/` | shared infrastructure: config loader, logging, caching, paths, exceptions |
| `script_engine/` | prompt → validated storyboard |
| `scene_engine/` | storyboard → scene plan + timing |
| `voice_engine/` | narration (TTS / voice cloning) |
| `avatar_engine/` | talking-avatar research + planning |
| `asset_engine/` · `media_intelligence/` | asset resolution + content-driven editing |
| `editing_engine/` · `caption_engine/` · `branding_engine/` · `music_engine/` | timeline composition |
| `reel_engine/` | rendering (mock + FFmpeg) and per-platform export profiles |
| `workflow_engine/` | the deterministic prompt-to-export orchestrator |
| `quality_engine/` | deterministic reel quality checks |
| `upload_engine/` | upload-ready metadata generation |
| `content_library/` | local single-user project + content store |
| `docs/` | architecture and per-engine documentation |

**Engineering rules:** engines depend on `foundation/`, never on each other's
internals; behaviour is configuration-driven; heavy ML deps are optional extras
so the core installs and tests with no GPU.

---

## Documentation

- [docs/VERSION_1.md](docs/VERSION_1.md) — **the Version 1.0 platform summary (start here)**
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — platform architecture and reuse map
- [docs/WORKFLOW_ENGINE.md](docs/WORKFLOW_ENGINE.md) — the deterministic orchestrator
- [quality_engine/docs/QUALITY_ENGINE.md](quality_engine/docs/QUALITY_ENGINE.md) — the quality checks
- [upload_engine/docs/UPLOAD_ASSISTANT.md](upload_engine/docs/UPLOAD_ASSISTANT.md) — upload metadata
- [docs/CONTENT_LIBRARY.md](docs/CONTENT_LIBRARY.md) · [docs/PERFORMANCE.md](docs/PERFORMANCE.md)
- [voice_engine/docs/INSTALLATION.md](voice_engine/docs/INSTALLATION.md) — installing real voice/avatar models (advanced)

---

## Scope

**Version 1.0 is intentionally small and local.** In scope: one creator, one
machine (VS Code or Colab), one reel per command, no cloud.

The following are **future enhancements, not part of Version 1.0**: batch
generation, cloud deployment, automatic publishing, and analytics.
