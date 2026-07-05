# Avatar benchmark assets

Scenario definitions live in `../scenarios.yaml`; this directory holds the
binary assets they reference. Nothing here is committed except this README —
assets are generated or supplied locally.

## Required files

| File | Used by | How to produce |
|---|---|---|
| `default_portrait.png` | every scenario without an explicit `source_image` | Licensed/consented frontal portrait, ≥512×512, neutral expression, even lighting |
| `portrait_three_quarter.png` | `side-pose-en` | Same subject, ~30–45° yaw |
| `portrait_stylized.png` | `stylized-avatar-en` | Illustration or 3D render of a presenter |
| `<scenario-id>.wav` | each scenario's driving audio | Generate with the voice engine (below) |

## Generating driving audio with the voice engine

Use the Phase A1 winner (or any installed adapter) to synthesize each
scenario script, e.g.:

```python
from avatar_engine.datasets import AvatarDatasetManager
from voice_engine.adapters import create_adapter
from voice_engine.interfaces import SynthesisRequest
from foundation.constants import Language

manager = AvatarDatasetManager()
dataset = manager.load()
adapter = create_adapter("melotts")  # any available adapter
for scenario in dataset.scenarios:
    assets = manager.resolve_assets(scenario)
    if assets.driving_audio.exists():
        continue
    adapter.synthesize(SynthesisRequest(
        text=scenario.script_text,
        language=Language.from_code(scenario.language),
        output_path=assets.driving_audio,
    ))
```

## Placeholders

`AvatarDatasetManager.generate_placeholder_assets()` writes sine-tone WAVs
and stub images for any missing file so the pipeline runs end-to-end before
real assets exist. Placeholder results are only good for wiring tests —
never quote metrics from placeholder runs.

## Consent and licensing

Portraits must be either owned by the team with written consent of the
subject, or licensed stock explicitly permitting ML processing. Record the
provenance of every portrait in this table when adding it.
