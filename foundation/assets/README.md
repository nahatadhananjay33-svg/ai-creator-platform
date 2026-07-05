# foundation/assets

Shared static assets (fonts, watermarks, brand kits, silence/tone reference
clips) used by multiple engines. Engine-specific assets belong inside the
engine (e.g. `voice_engine/datasets/reference_audio/`).

Keep binary assets small; large binaries belong in object storage referenced
by `foundation/model_manager` specs.
