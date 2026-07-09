# Demos

Runnable demos for stakeholders. Never imported by production code.

## Caption Engine (Phase C4)

Full slice — script → talking-head video → native caption track → playable MP4
plus SRT / WebVTT / JSON / Timeline caption exports:

```
python -m caption_engine.scripts.render_caption_demo                 # real MP4 (ffmpeg)
python -m caption_engine.scripts.render_caption_demo --renderer mock # hermetic proxy
python -m caption_engine.scripts.render_caption_demo --kind sentence --preset youtube
```

See `docs/CAPTION_ENGINE.md` for architecture, styles, and limitations.

## Branding & Theme Engine (Phase C5)

Full slice — script → talking-head video → captions → native branding track
(intro, logo, lower third, watermark, outro) → playable MP4:

```
python -m branding_engine.scripts.render_branding_demo                  # real MP4 (ffmpeg)
python -m branding_engine.scripts.render_branding_demo --renderer mock  # hermetic proxy
python -m branding_engine.scripts.render_branding_demo --theme finance
```

See `docs/BRANDING_ENGINE.md` for architecture, the theme system, and limitations.

## Visual Asset Engine (Phase C6)

Full slice — talking-head → image B-roll → talking-head → video B-roll, plus
picture-in-picture and split-screen, as a native Timeline asset track:

```
python -m asset_engine.scripts.render_asset_demo                  # real MP4 (ffmpeg)
python -m asset_engine.scripts.render_asset_demo --renderer mock  # hermetic proxy
python -m asset_engine.scripts.render_asset_demo --no-overlays    # assets only
```

See `docs/VISUAL_ASSET_ENGINE.md` for architecture, layouts, and limitations.

## Review & Editing Engine (Phase C11)

Human-in-the-loop editing — prompt → AI storyboard → review → immutable patch
set → incremental plan → updated playable MP4 (no whole-reel rebuild):

```
python -m editing_engine.scripts.render_edit_demo                  # real MP4 (ffmpeg)
python -m editing_engine.scripts.render_edit_demo --renderer mock  # hermetic proxy
```

See `docs/EDITING_ENGINE.md` for the editable model, patches, and limitations.

## Creator Studio (Phase C12)

The deterministic visual editor (interface layer over the Editing Engine) —
open → storyboard/timeline → edit via immutable patches → incremental
regeneration → preview → export an updated reel:

```
python -m creator_studio.scripts.render_studio_demo                  # real MP4 (ffmpeg)
python -m creator_studio.scripts.render_studio_demo --renderer mock  # hermetic proxy
```

See `docs/CREATOR_STUDIO.md` for the panels, patch integration, and limitations.
