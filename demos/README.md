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
