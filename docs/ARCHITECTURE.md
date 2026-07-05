# AI Creator Platform — Architecture

## Layering

```
┌─────────────────────────────────────────────────────────────┐
│  Products (A5-A7+): Reel generator · Talking avatars ·      │
│  Real-estate voice agents · WhatsApp voice                  │
├─────────────────────────────────────────────────────────────┤
│  Engines: voice_engine · avatar_engine · script_engine ·    │
│  caption_engine · reel_engine · export                      │
├─────────────────────────────────────────────────────────────┤
│  foundation: config · logging · exceptions · constants ·    │
│  shared_utils · cache · model_manager · benchmarking        │
└─────────────────────────────────────────────────────────────┘
```

Rules:

1. `foundation` imports nothing from engines.
2. Engines import `foundation` freely; engines talk to each other **only**
   through each other's `interfaces/` packages (e.g. avatar_engine consumes
   `voice_engine.interfaces.SynthesisResult`, never an adapter class).
3. Products compose engines; no business logic inside engines.
4. Benchmarks orchestrate production modules — there is no benchmark-only
   model code anywhere.
5. Heavy ML dependencies are optional extras; the repo installs and tests
   green with zero of them present.

## Voice Engine internals (Phase A1 + A1.5 state)

```
voice_engine/
  interfaces/   TTSEngine · VoiceCloner · StreamingTTSEngine · value types  [FROZEN CONTRACT]
  adapters/     BaseVoiceAdapter + one adapter per model (spec = metadata SoT)
  models/       catalog views · install_specs (per-model venv recipes) · validation (ModelValidator)
  datasets/     EN/HI/Hinglish/BN prompt corpora + DatasetManager + reference_audio/
  metrics/      stdlib audio stats · performance · text/script metrics · similarity (optional)
  evaluation/   metric catalog (auto vs human) · SynthesisEvaluator · blind listening protocol
  benchmark/    config + scenario cases + orchestrator (composition only)
  reporting/    CSV · JSON · Markdown reporters + run summarizer
  cloning/      reference_validation (duration study; seeds A2 intake pipeline)
  scripts/      run_benchmark · merge_runs · install_models · validate_models ·
                generate_reference_clips · reference_study · validate_references
  output/       runs/ · installs/ · validation/ (gitignored artifacts + reports)
  research/     model research docs
  docs/         installation · hardware · recommendations · A2 roadmap
  tts/ streaming/ pronunciation/ emotion/ voices/ pipelines/   [A2 packages, interfaces frozen now]
```

### Model installation architecture (Phase A1.5)

- ``foundation.model_manager.environment``: machine probe (CPU/RAM/GPU/driver/
  CUDA/torch/disk) + per-ModelSpec compatibility verdicts (gpu / cpu /
  cpu-offline / none).
- ``foundation.model_manager.installer``: generic resumable installer —
  **one venv per model** (`.venvs/<model_id>/`, uv-managed, shared wheel
  cache), pip groups with retry, import verification inside the target venv,
  status persisted in ``foundation.cache``.
- ``voice_engine/models/install_specs.py``: the voice-specific recipes,
  including empirically resolved pins (each pin documents why it exists).
- Benchmarks execute *inside* a model's venv
  (``.venvs\<id>\Scripts\python.exe -m voice_engine.scripts.run_benchmark``);
  ``merge_runs`` combines per-venv runs into one comparison report.

## How future phases reuse Phase A1 components

| Component | A2 Voice | A3/A4 Avatar | A5 Reels | A6 Streaming | A7 RE Voice AI |
| --- | --- | --- | --- | --- | --- |
| foundation.config/logging/exceptions | ✓ | ✓ | ✓ | ✓ | ✓ |
| foundation.model_manager (specs/registry/device) | ✓ | ✓ (face/lip models register here) | ✓ | ✓ | ✓ |
| foundation.cache | synthesis cache | frame/embedding cache | render cache | latent cache | response cache |
| foundation.benchmarking | model benchmarks | avatar benchmarks | pipeline perf | latency SLOs | call-quality monitoring |
| voice_engine.interfaces | served | consumed (audio for lip-sync) | consumed | consumed | consumed |
| voice_engine.adapters | served in prod | — | — | streaming subset | streaming subset |
| voice_engine.datasets | regression suite | lip-sync test audio | — | latency corpus | agent phrase tests |
| voice_engine.evaluation/reporting | regression gates | A/V eval extends Measurement | QA reports | SLO reports | QA reports |

The key mechanism: **`Measurement`/`CaseResult`/`RunResult` are
engine-agnostic**, so every future engine gets benchmarking + reporting for
free by writing `BenchmarkCase` subclasses, exactly as the voice benchmark
did.

## Configuration & observability conventions

- YAML config bound to dataclasses (`foundation.config.ConfigLoader.bind`);
  env overrides via `AICP__section__key`.
- Loggers: `get_logger("engine.component")` under the `aicp` namespace;
  JSON format in services, text in dev.
- All runtime artifacts under gitignored paths defined in
  `foundation/constants/paths.py`.

## Testing strategy

- Unit tests per package (`foundation/tests`, `voice_engine/tests`), all
  runnable with zero ML deps (mock adapter proves the full pipeline).
- Heavy-model correctness is validated by the benchmark itself (SKIPPED vs
  PASSED vs FAILED semantics), keeping CI light and hardware-bound
  verification explicit.
