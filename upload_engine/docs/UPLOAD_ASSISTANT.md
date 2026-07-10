# Upload Assistant — Simple Local Upload Metadata (Phase C18)

The Upload Assistant is a small helper that runs **after a reel is rendered and
passes quality**. Given a finished reel it produces the copy a creator pastes into
each platform, plus two files that make copy-paste trivial.

It is deliberately simple and honest:

- **local-only, single-user** — no cloud, **no OAuth**, no social-media APIs, no
  network. Nothing is ever posted; it only writes local files you paste yourself;
- **deterministic** — the words come from the reel's **own storyboard** (title,
  hook, per-scene narration, keywords); a per-vertical template adds only
  *presentation* (a lead emoji, hashtags, per-platform call-to-action lines). **No
  AI, no scoring, no automatic publishing, no scheduling, no analytics**;
- **read-only** — it changes **no** engine and **no** artifact. It only *reads* the
  finished run and *writes* the two upload files.

```
Workflow Engine ─► Quality PASS ─► Upload Assistant ─► metadata.json + upload_preview.md
```

## What it generates

From a finished reel the assistant produces **eight** upload-ready outputs:

| Output | Built from | Notes |
|---|---|---|
| **YouTube Title** | storyboard title (else prompt) | collapsed to one line, ≤ 100 chars |
| **YouTube Description** | hook + narration + CTA + hashtags | full paragraph layout |
| **Instagram Caption** | emoji + hook + short body + CTA + hashtags | ≤ 2200 chars |
| **Facebook Caption** | hook + short body + CTA + few hashtags | fewer tags read better |
| **LinkedIn Post** | hook + "Key takeaways" bullets + CTA + few hashtags | professional layout |
| **Hashtags** | scene keywords, then the template's tags | topical-first, deduped, capped |
| **Thumbnail Text** | punchy words from the title (else hook) | short, UPPERCASE |
| **Suggested Filename** | slug of the title (else prompt) | lowercase, safe, `.mp4` |

Every output has a **fallback**, so none can come out empty — a reel with only a
prompt still yields a complete set. `UploadMetadata.missing_fields()` reports any
required output that came out empty (it never should); the CLI treats a non-empty
result as a failure.

### Where the words come from

The generator never invents copy. It mines a [`ReelSummary`](../assistant/summary.py)
from the run's `AIStoryboard` — `title`, `hook`, each scene's `narration` and
`keywords`, and the call-to-action lines — plus two render facts (duration, aspect)
from the Timeline. A template contributes only presentation, so **the same reel
always produces the same metadata** and swapping a template never changes the
underlying message, only its framing.

## Templates (editable, one per vertical)

Templates live in [`templates/templates.yaml`](../templates/templates.yaml) — a
`defaults` block every vertical inherits, plus a small override per vertical. Adding
or tuning a vertical is a **YAML edit, no code change**.

| Vertical | Emoji | Example vertical hashtags |
|---|---|---|
| `general` | 🎬 | #tips #howto #learn |
| `real_estate` | 🏡 | #realestate #property #investing |
| `finance` | 💰 | #finance #investing #money |
| `education` | 📚 | #education #learning #study |
| `medical` | 🩺 | #health #wellness #healthcare |

Each template supplies a lead `emoji`, its `hashtags` (merged **vertical-first**,
then the defaults' generic tags, deduped and capped by `hashtag_limit`), the four
per-platform CTAs (`youtube_cta` / `instagram_cta` / `facebook_cta` / `linkedin_cta`),
and a `thumbnail_max_words` budget. An unknown or blank vertical name falls back to
`general`, so metadata generation never fails on an odd label. When no template is
passed, the reel's **own** `storyboard.template` is used.

## Outputs

The assistant writes two files (see [`assistant/outputs.py`](../assistant/outputs.py)):

- **`metadata.json`** — machine-readable, one field per output (pretty JSON, UTF-8,
  stable key order). Round-trips `UploadMetadata.to_dict()`.
- **`upload_preview.md`** — human-readable and **copy-paste-ready**: each output sits
  in its own fenced block so you can copy a whole caption in one go and paste it
  straight into YouTube / Instagram / Facebook / LinkedIn.

Both are written deterministically, so the same reel yields **byte-identical** files.

## Usage

### CLI

```
# hermetic (mock renderer): generate one reel + its metadata
python -m upload_engine.scripts.generate_metadata

# choose a vertical / prompt, or print the metadata JSON
python -m upload_engine.scripts.generate_metadata --template finance --prompt "..."
python -m upload_engine.scripts.generate_metadata --json
```

The CLI walks the full flow: render a reel (mock backend — **no GPU, no ffmpeg, no
network**), **quality-gate it** (it refuses to emit metadata unless quality PASSes),
generate the eight outputs, write the two files, and validate them.

Exit codes: `0` = metadata written & complete, `2` = quality FAIL or an empty
output, `1` = usage / environment error.

### Library

```python
from upload_engine import generate_upload_metadata, ReelSummary, write_upload_assets

summary = ReelSummary(title="5 tips for better sleep", prompt="...", template="medical")
metadata = generate_upload_metadata(summary)          # the eight outputs
print(metadata.youtube_title, metadata.hashtags)
write_upload_assets(metadata, "out/")                 # metadata.json + upload_preview.md
```

### Workflow Engine gate

```python
from workflow_engine import WorkflowEngine
from quality_engine import check_workflow_result
from upload_engine import generate_upload_assets

result = WorkflowEngine(root="run").run(workflow, run_id="run")
if check_workflow_result(result).ok:                  # only after Quality PASS
    metadata, files = generate_upload_assets(result, "run/upload", template="real_estate")
    #        files.metadata_json  /  files.preview_md
```

[`workflow_link.py`](../workflow_link.py) is the single, **read-only** integration
point: `summary_from_result` / `generate_from_result` / `generate_upload_assets`.

## Configuration

[`UploadConfig`](../assistant/config.py) holds the platform limits and knobs:

| Field | Default | Meaning |
|---|---|---|
| `youtube_title_max` | 100 | YouTube title character limit |
| `instagram_caption_max` | 2200 | Instagram caption character limit |
| `filename_max` | 80 | keep suggested filenames short & safe |
| `description_body_lines` | 6 | narration lines folded into a description |
| `caption_body_lines` | 3 | narration lines folded into a caption |
| `facebook_hashtag_max` / `linkedin_hashtag_max` | 5 / 5 | fewer tags on FB/LinkedIn |
| `thumbnail_fallback` | `WATCH NOW` | used only when no words can be mined |

## Layout

```
upload_engine/
├── __init__.py                 # public API
├── assistant/
│   ├── config.py               # UploadConfig (limits/knobs)
│   ├── summary.py              # ReelSummary — mine the reel's words + facts
│   ├── text.py                 # clamp / hashtagify / thumbnail helpers
│   ├── generate.py             # one deterministic generator per output
│   ├── metadata.py             # UploadMetadata (+ missing_fields validation)
│   ├── outputs.py              # write metadata.json + upload_preview.md
│   └── engine.py               # UploadAssistant facade
├── templates/
│   ├── templates.yaml          # editable per-vertical templates
│   └── registry.py             # UploadTemplate loader
├── workflow_link.py            # read a WorkflowResult (read-only)
├── scripts/generate_metadata.py  # CLI
├── tests/                      # hermetic — no APIs, no GPU
└── docs/UPLOAD_ASSISTANT.md    # this file
```

## Tests

All tests are **hermetic**: no APIs, no network, no GPU. Generation is covered with
a duck-typed storyboard stub; a single end-to-end test renders one real reel with
the **mock** backend, quality-gates it, and asserts the metadata is complete and the
two files are written — which is the phase's validation.

## Scope (deliberately out)

The Upload Assistant only **generates metadata**. It does **not** post, schedule, or
authenticate anything: no automatic posting, no OAuth, no scheduling, no analytics,
no social-media APIs. Those belong to future versions.
