# AI Prompt & Storyboard Engine (Phase C10)

The Script Engine is the **AI front of the pipeline**. It turns a natural-language
**prompt** into a validated, structured **AI Storyboard** and feeds it into the
existing **deterministic** Scene Engine (Phase C7) — which owns all scene
planning, timing, and visual slotting. Everything downstream is reused unchanged.

The AI layer's responsibility is deliberately narrow. It **does NOT**:
- generate video,
- modify the Timeline IR,
- talk to the renderer,
- or re-implement any scene-planning logic.

It only produces the structured brief:

```
prompt ─► provider ─► AI Storyboard ─► validate ─► script ─► Scene Engine
       ─► deterministic Storyboard ─► Timeline IR ─► existing pipeline ─► MP4
```

Multiple providers sit behind one interface and **all emit the same structured
output**; the deterministic **MockProvider is the default**, so the entire
pipeline runs — and is tested — with **no API key**.

## Architecture

Reuses the platform foundation (config, logging, benchmarking) and the entire
existing pipeline. It depends on the Scene Engine (and, in the demo, the
Branding/Asset/Music engines) — never the reverse.

| Package | Responsibility |
|---|---|
| `script_engine/storyboard/` | The frozen **AI Storyboard IR** (`AIStoryboard`/`ScriptScene`) + serde + the JSON schema for LLMs + `storyboard_to_script` (the seam into the Scene Engine) |
| `script_engine/validator/` | Explicit validation of AI output → problem list / `ScriptValidationError` |
| `script_engine/prompt_templates/` | Configuration-driven templates (`templates.yaml`) + `PromptTemplate` registry |
| `script_engine/providers/` | The `StoryboardProvider` interface + `MockProvider` (deterministic) + OpenAI/Anthropic/Gemini (real, lazy) |
| `script_engine/planner/` | `ScriptEngine` facade: prompt → AIStoryboard → Scene Engine → Timeline |
| `script_engine/config/` | `defaults.yaml` bound to a frozen `ScriptEngineConfig` |
| `script_engine/benchmark/` | Deterministic prompt-to-reel benchmark |
| `script_engine/scripts/` | `render_script_demo`, `run_benchmark` CLIs |

## Provider abstraction

Every provider — deterministic and LLM-backed — implements one interface:

```python
class StoryboardProvider(Protocol):
    name: str
    def generate(self, request: GenerationRequest) -> AIStoryboard: ...
```

`get_provider(name)` is the factory; the real providers are **imported lazily**,
so the Mock path (and the whole hermetic suite) never needs their SDKs or keys.

| Provider | Source | Notes |
|---|---|---|
| `MockProvider` | template + prompt | Deterministic template filling — **no AI, no network, no key**. The hermetic default. |
| `AnthropicProvider` | Claude API | Default model `claude-opus-4-8`; structured outputs via `output_config.format`; **no `temperature`** (rejected on modern Claude); reads `ANTHROPIC_API_KEY` or an `ant auth` profile. |
| `OpenAIProvider` | OpenAI API | `chat.completions` with `response_format` json-schema (strict); reads `OPENAI_API_KEY`. |
| `GeminiProvider` | Gemini API | `response_mime_type=application/json` + `response_schema`; reads `GEMINI_API_KEY`. |

All four request JSON matching `AI_STORYBOARD_JSON_SCHEMA` and parse it into the
**same** `AIStoryboard`, so they are fully interchangeable. Adding a fifth
provider is one class implementing `generate` + one line in `get_provider`.

## Prompt templates

Templates are **configuration-driven** (`prompt_templates/templates.yaml`) — one
per content vertical. Adding a vertical is a YAML edit, no code change:

**general, real_estate, finance, medical, education, news, motivational,
talking_head.**

Each template supplies:
- `audience` / `tone` — framing carried onto the storyboard,
- `system_prompt` — the instruction a **real** LLM provider receives,
- `arc` — the advisory scene-type sequence (hook … call_to_action),
- `hook` / `cta` / `body` — deterministic narration lines the **MockProvider**
  fills with the prompt's topic (body lines carry keyword triggers so the
  deterministic Scene Engine classifies a varied reel).

## Storyboard schema

`AIStoryboard` is the frozen structured brief every provider emits — the example
output shape from the objective:

| Field | Meaning |
|---|---|
| `title` | reel title |
| `target_audience` | who it's for |
| `tone` | overall tone |
| `hook` | the opening line (also scene 0's narration) |
| `scenes[]` | ordered `ScriptScene`s |
| `prompt` / `template` / `provider` / `model` | provenance |

Each `ScriptScene` carries: `narration`, `scene_type`, `asset_type`, `layout`,
`cta`, `duration_estimate_s`, `keywords`. Only `narration` is strictly needed
downstream — the rest are **suggestions**; the deterministic Scene Engine remains
authoritative for the actual plan (it re-classifies and re-times from the
narration). `duration`/`word`/`type` stats are derived, never stored.

### The seam into the deterministic pipeline

`storyboard_to_script` lowers the brief to a **marker-delimited script** — each
scene's narration separated by the Scene Engine's `---` manual scene marker. The
existing `SceneEngine.plan(script)` then segments, classifies, times, and plans
visuals. **No scene-planning logic is duplicated** — the AI decides *what to say
and how to break scenes*; the deterministic layer does everything else.

## Validation

AI output is untrusted, so a generated storyboard is validated before it enters
the pipeline. `validate_storyboard` returns explicit problems (empty == valid);
`validate_or_raise` raises `ScriptValidationError` with all of them:

- **required fields** — title present, scenes non-empty,
- **scene count** within `[min_scenes, max_scenes]`,
- **duration estimates** non-negative (and total within a sane bound),
- **no empty narration**,
- **no duplicate scenes** (identical narration),
- **only supported scene types** (the Scene Engine's closed set),
- (plus a per-scene word cap to catch runaway output).

## Configuration

`script_engine/config/defaults.yaml`, layered like every engine (`AICP__script__*`
env / user file / overrides). Provider **API keys are read from the environment
at call time** — never stored in config, so the hermetic path never needs one.

| Key | Default | Meaning |
|---|---|---|
| `provider` | `mock` | `mock` \| `openai` \| `anthropic` \| `gemini` |
| `model` | `""` | empty → the provider's own default |
| `temperature` | `0.7` | sampling (ignored by providers that reject it) |
| `min_scenes` / `max_scenes` | `3` / `8` | scene-count bounds (validation) |
| `target_duration_s` | `40.0` | aim for roughly this reel length |
| `language` / `style` | `en` / `informative` | narration hints |
| `template` | `general` | default prompt template |
| `max_tokens` | `4096` | provider output cap |

## Usage

```python
from script_engine import ScriptEngine

engine = ScriptEngine()                                  # MockProvider by default
ai_storyboard = engine.generate_storyboard("Why investing in real estate early is beneficial",
                                           template="real_estate")   # validated
ai_sb, scene_sb = engine.plan("How compound interest works", template="finance")
ai_sb, scene_sb, timeline = engine.plan_timeline("Three habits that improve focus")

# a real provider (needs the SDK + key):
engine = ScriptEngine(config=ScriptEngineConfig(provider="anthropic"))
```

## Demo & validation

```
python -m script_engine.scripts.render_script_demo                  # ffmpeg MP4 (mock provider)
python -m script_engine.scripts.render_script_demo --renderer mock  # hermetic proxy
python -m script_engine.scripts.render_script_demo --provider anthropic --template finance  # live LLM
```

From a prompt the demo generates an AI storyboard, feeds it through the Scene
Engine, stacks the full pipeline (captions + branding + resolved visual assets +
music), and renders a playable MP4 + `reel_9x16`/`square_1x1` exports. It
verifies (backend-independent): the **storyboard is valid**, the **scene plan is
valid** (correct scene count, no gaps/overlaps), the **timeline validates**, the
mock run is **byte-identical** on replan, and the master + exports are playable —
i.e. *an AI-generated storyboard successfully produces a playable reel with no
pipeline failures*.

## Benchmark

```
python -m script_engine.scripts.run_benchmark
```

Measures provider latency, storyboard generation, validation, scene generation,
timeline generation, total pipeline time, and memory over a fixed prompt set.
Hermetic (MockProvider) — no AI, no GPU, no network, no key.

## Regression tests

`script_engine/tests/` — hermetic and deterministic (MockProvider only). Cover
the storyboard IR + serde, the validator, all 8 templates, provider determinism +
interface conformance (incl. the real providers construct behind the interface),
the script seam, and the `ScriptEngine` facade end to end. The only tests that
touch a real API live in `test_integration_live.py` and are **skipped** unless
the provider SDK + key are present.

```
python -m pytest script_engine/tests -q
```

## Limitations (Phase C10 scope)

- **AI produces the brief only** — never video, never Timeline IR, never renderer
  calls. All planning/timing/rendering stays in the existing deterministic layers.
- **Scene-type suggestions are advisory** — the deterministic Scene Engine
  re-derives the authoritative type from the narration; a provider's `scene_type`
  is carried for reporting.
- **MockProvider is a template filler**, not a language model — it exists so the
  pipeline is deterministic and key-free. The real providers deliver genuine
  generation with a live key.
- **ffmpeg captions dislike apostrophes** — a pre-existing renderer limitation
  (unchanged in C10); the demo uses apostrophe-free narration.

## Future improvements

The provider seam and frozen storyboard shape were built so more capability drops
in without touching the deterministic pipeline:

- **More providers** — a new `StoryboardProvider` (e.g. a local model, a
  fine-tuned endpoint) is one class + one `get_provider` line.
- **Richer briefs** — the AI could populate `asset_type` / `layout` more
  precisely to bias the C9 Asset Resolver, or emit per-scene music/tone cues for
  the C8 Music Engine — all additive to `ScriptScene`.
- **Honouring AI timing** — feed the AI's `duration_estimate_s` into the Scene
  Engine's `known_durations` when the AI scene count is preserved 1:1.
- **Iterative refinement / critique** — a validate → re-prompt loop that asks the
  provider to fix flagged problems before the brief enters the pipeline.
- **Caching & batching** — cache prompt→storyboard by content hash; batch many
  prompts through the Batches API for bulk generation.

None of these change the deterministic Scene Engine, the Timeline IR, or the
renderer — they only change how the brief is produced.
