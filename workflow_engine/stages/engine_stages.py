"""The engine stages (Phase C14) — each wraps ONE existing engine, no logic copied.

Every stage below only calls the public API of an already-shipped engine and emits
immutable, content-addressed :class:`Artifact` values. Nothing here modifies the
Timeline IR, the renderer, or any engine; the workflow is pure composition.

    Storyboard ─► Scene Planning ─► Voice ─► Avatar ─► Assets
               ─► Media Intelligence ─► Editing ─► Timeline ─► Renderer ─► Export

Cache keys are content hashes chosen to reflect *what actually determines a stage's
output* (e.g. a project hashes by its storyboard + presentation, not its revision
counter; a master hashes by renderer + timeline hash + profiles, not the encoded
bytes) so incremental reuse is correct even when a backend's byte output is not
bit-reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reel_engine.config import ReelEngineConfig, RenderConfig
from reel_engine.exporters.profiles import get_profile
from reel_engine.interfaces.types import RenderRequest
from reel_engine.render import ffprobe_available, get_renderer, probe_media
from reel_engine.timeline.hashing import timeline_content_hash
from reel_engine.timeline.serde import timeline_to_json

from editing_engine import EditingEngine
from media_intelligence import AssetRegistry, MediaIntelligenceEngine, RegisteredAsset
from media_intelligence.registry import make_asset_id
from script_engine import ScriptEngine
from script_engine.storyboard.serde import storyboard_to_dict
from voice_engine import VoiceEngine

from workflow_engine.core.artifact import (
    KIND_FILE,
    KIND_FILESET,
    KIND_JSON,
    KIND_PROJECT,
    KIND_STORYBOARD,
    KIND_TIMELINE,
    Artifact,
    hash_files,
    hash_json,
)
from workflow_engine.core.stage import WorkflowStage
from workflow_engine.stages.base import (
    Presentation,
    base_project,
    patch_from_spec,
    patch_to_spec,
)

# --------------------------------------------------------------------------- 1
@dataclass(frozen=True)
class StoryboardStage(WorkflowStage):
    """Prompt -> validated ``AIStoryboard`` via the AI Prompt & Storyboard Engine."""

    prompt: str = ""
    template: str = ""
    provider: str = "mock"

    def run(self, ctx):
        sb = ScriptEngine().generate_storyboard(
            self.prompt, template=self.template or None, provider=self.provider)
        art = Artifact("storyboard", KIND_STORYBOARD,
                       hash_json(storyboard_to_dict(sb)), value=sb,
                       meta={"scenes": sb.n_scenes, "provider": sb.provider,
                             "template": self.template})
        return self._single(art)


# --------------------------------------------------------------------------- 2
@dataclass(frozen=True)
class ScenePlanningStage(WorkflowStage):
    """``AIStoryboard`` -> deterministic Scene-Planner storyboard summary.

    Reuses ``EditingEngine.plan_scene_storyboard`` (which itself drives the Scene
    Engine); emits a JSON summary used for inspection and validation. Scene planning
    depends only on the storyboard + brand attribution (creator/channel) — *not* on
    theme/soundtrack/captions — so those are its only params and a presentation edit
    never spuriously invalidates it."""

    creator: str = ""
    channel: str = ""

    def run(self, ctx):
        project = base_project(ctx.value("storyboard"),
                               Presentation(creator=self.creator, channel=self.channel))
        scene_sb = EditingEngine().plan_scene_storyboard(project)
        summary = {
            "n_scenes": scene_sb.n_scenes,
            "duration_s": round(scene_sb.duration_s, 3),
            "scene_types": [str(getattr(s, "scene_type", "")) for s in scene_sb.scenes],
            "n_asset_slots": len(list(scene_sb.all_asset_slots)),
        }
        art = Artifact("scene_plan", KIND_JSON, hash_json(summary), value=summary,
                       meta={"n_scenes": summary["n_scenes"],
                             "duration_s": summary["duration_s"]})
        return self._single(art)


# --------------------------------------------------------------------------- 3
@dataclass(frozen=True)
class VoiceStage(WorkflowStage):
    """Synthesize each scene's narration to a WAV via the Voice Engine.

    Uses the dependency-free ``mock`` adapter by default so the stage is hermetic
    and deterministic; any installed adapter can be named instead."""

    model: str = "mock"
    language: str = "en"
    speed: float = 1.0

    def run(self, ctx):
        sb = ctx.value("storyboard")
        out_dir = ctx.stage_dir(self.name)
        engine = VoiceEngine()
        engine.load_model(self.model)
        paths: list[Path] = []
        for i, scene in enumerate(sb.scenes):
            wav = out_dir / f"scene_{i:03d}.wav"
            engine.generate(scene.narration, language=self.language, speed=self.speed,
                            model_id=self.model, output_path=wav, use_cache=False)
            paths.append(wav)
        files = tuple(paths)
        art = Artifact("voice", KIND_FILESET, hash_files(files), value=files,
                       meta={"n_clips": len(files), "model": self.model,
                             "language": self.language})
        return self._single(art)


# --------------------------------------------------------------------------- 4
@dataclass(frozen=True)
class AvatarStage(WorkflowStage):
    """A deterministic per-scene avatar *plan* (the seam for the Avatar Engine).

    The Avatar Engine currently ships research infrastructure only (no production
    generation API, Phase A3), so this stage cannot invoke a talking-head model
    without changing an engine. It instead produces a deterministic avatar plan —
    one entry per narration clip (its driving audio, target frame, style) — which is
    exactly the input a future Avatar Engine production API will consume. Documented
    limitation; no engine is modified."""

    style: str = "reference"
    enabled: bool = True

    def run(self, ctx):
        voice_files = ctx.value("voice") or ()
        plan = {
            "enabled": self.enabled,
            "style": self.style,
            "clips": [
                {"index": i, "audio": Path(p).name, "style": self.style,
                 "status": "planned"}
                for i, p in enumerate(voice_files)
            ],
            "note": "avatar generation deferred to Avatar Engine production API (Phase A4)",
        }
        art = Artifact("avatar", KIND_JSON, hash_json(plan), value=plan,
                       meta={"n_clips": len(plan["clips"]), "enabled": self.enabled})
        return self._single(art)


# --------------------------------------------------------------------------- 5
#: A small deterministic default library so Media Intelligence yields real, hermetic
#: recommendations. A production workflow points the Assets stage at a real library.
DEFAULT_ASSETS: tuple[dict, ...] = (
    {"uri": "lib/city_skyline.mp4", "kind": "video",
     "tags": ("city", "skyline", "property", "growth"), "duration_s": 12.0},
    {"uri": "lib/property_growth.jpg", "kind": "image",
     "tags": ("property", "growth", "invest", "home")},
    {"uri": "lib/chart_returns.png", "kind": "chart",
     "tags": ("returns", "growth", "numbers", "finance")},
    {"uri": "lib/keys_home.jpg", "kind": "image",
     "tags": ("keys", "home", "buy", "early")},
    {"uri": "lib/handshake.jpg", "kind": "image",
     "tags": ("deal", "trust", "agent", "closing")},
    {"uri": "lib/map_location.png", "kind": "map",
     "tags": ("location", "map", "neighborhood")},
)


def _asset_from_dict(d: dict) -> RegisteredAsset:
    w, h = int(d.get("width", 1920)), int(d.get("height", 1080))
    dur = float(d.get("duration_s", 0.0))
    uri, kind = d["uri"], d["kind"]
    return RegisteredAsset(
        asset_id=make_asset_id(kind, uri, w, h, dur), uri=uri, kind=kind,
        tags=tuple(d.get("tags", ())), width=w, height=h, duration_s=dur,
        source=d.get("source", "library"), license=d.get("license", "cc0"),
        meta=dict(d.get("meta", {})))


@dataclass(frozen=True)
class AssetsStage(WorkflowStage):
    """Build the available-asset registry the Media Intelligence stage searches.

    Reuses the C13 ``AssetRegistry``; assets are carried as an immutable tuple of
    descriptors (defaulting to a small deterministic library) and emitted as a JSON
    artifact so the registry round-trips for resume."""

    assets: tuple = DEFAULT_ASSETS

    def run(self, ctx):
        registry = AssetRegistry([_asset_from_dict(d) for d in self.assets])
        payload = {"assets": [
            {"uri": a.uri, "kind": a.kind, "tags": list(a.tags), "width": a.width,
             "height": a.height, "duration_s": a.duration_s, "source": a.source,
             "license": a.license, "meta": a.meta}
            for a in registry.all()]}
        art = Artifact("assets", KIND_JSON, hash_json(payload), value=payload,
                       meta={"n_assets": registry.size})
        return self._single(art)


# --------------------------------------------------------------------------- 6
@dataclass(frozen=True)
class MediaIntelligenceStage(WorkflowStage):
    """Deterministic media decisions -> a serializable list of editing patches.

    Reuses the C13 ``MediaIntelligenceEngine``: builds the registry from the
    ``assets`` artifact, plans over the base project, and lowers the plan's
    immutable patches to JSON specs (fully resumable). Media *recommendations* are
    content-driven (narration + available assets), independent of the chosen
    theme/soundtrack, so the stage takes no presentation param — it recommends those
    choices rather than depending on them."""

    language: str = "en"
    n_alternatives: int = 2

    def run(self, ctx):
        assets_payload = ctx.value("assets")
        registry = AssetRegistry([_asset_from_dict(d) for d in assets_payload["assets"]])
        project = base_project(ctx.value("storyboard"), Presentation())
        engine = MediaIntelligenceEngine(registry)
        plan = engine.plan(project, language=self.language,
                           n_alternatives=self.n_alternatives)
        specs = [patch_to_spec(p) for p in plan.patches()]
        payload = {
            "patches": specs,
            "music": {"soundtrack": plan.music.soundtrack,
                      "reason": getattr(plan.music, "reason", "")},
            "voice": {"narrator": getattr(plan.voice, "narrator", ""),
                      "language": self.language},
            "consistency_score": round(float(getattr(plan.consistency, "score", 0.0)), 4),
        }
        art = Artifact("media_plan", KIND_JSON, hash_json(payload), value=payload,
                       meta={"n_patches": len(specs),
                             "soundtrack": payload["music"]["soundtrack"]})
        return self._single(art)


# --------------------------------------------------------------------------- 7
@dataclass(frozen=True)
class EditingStage(WorkflowStage):
    """Apply the media-plan patches (+ any explicit edits) -> the edited project.

    Reuses the C11 ``EditingEngine``; each patch validates before it applies and
    yields a new immutable ``ReelProject`` (the input is never mutated)."""

    presentation: Presentation = Presentation()
    apply_media: bool = True
    extra_patches: tuple = ()          # tuple[dict] of patch specs

    def run(self, ctx):
        engine = EditingEngine()
        project = base_project(ctx.value("storyboard"), self.presentation)
        specs: list[dict] = []
        if self.apply_media:
            specs.extend(ctx.value("media_plan").get("patches", []))
        specs.extend(self.extra_patches)
        applied = 0
        for spec in specs:
            patch = patch_from_spec(spec)
            problems = patch.validate(project)
            if problems:                       # skip a stale/inapplicable suggestion
                continue
            project = engine.apply(project, patch)
            applied += 1
        content = hash_json({"sb": storyboard_to_dict(project.storyboard),
                             "pres": self.presentation.to_dict()})
        art = Artifact("project", KIND_PROJECT, content, value=project,
                       meta={"revision": project.revision, "patches_applied": applied,
                             "n_scenes": project.n_scenes})
        return self._single(art)


# --------------------------------------------------------------------------- 8
@dataclass(frozen=True)
class TimelineStage(WorkflowStage):
    """Lower the edited project to the EXISTING Timeline IR (reusing every engine).

    Reuses ``EditingEngine.build_timeline`` — captions/branding/music come from the
    project's own settings; the Timeline IR is unchanged. Emits the Timeline as a
    content-addressed artifact keyed by the engine's own ``timeline_content_hash``."""

    with_branding: bool = True
    with_music: bool = True
    with_assets: bool = False

    def run(self, ctx):
        project = ctx.value("project")
        out_dir = ctx.stage_dir(self.name)
        _scene_sb, timeline = EditingEngine().build_timeline(
            project, with_branding=self.with_branding, with_music=self.with_music,
            with_assets=self.with_assets, asset_dir=out_dir)
        art = Artifact("timeline", KIND_TIMELINE, timeline_content_hash(timeline),
                       value=timeline,
                       meta={"n_scenes": timeline.n_scenes,
                             "duration_s": round(timeline.duration_s, 3),
                             "has_captions": timeline.has_captions,
                             "has_music": timeline.has_music})
        return self._single(art)


# --------------------------------------------------------------------------- 9
@dataclass(frozen=True)
class RenderStage(WorkflowStage):
    """Render the Timeline to a master (+ platform renditions) via the EXISTING renderer.

    One deterministic ``render()`` pass emits the master and every requested export
    profile together (the engine's native mode). The ``mock`` backend writes a
    hermetic raw-AVI proxy; ``ffmpeg`` writes a real MP4. The master's content hash
    is the *logical* render identity (renderer + timeline hash + profiles), so the
    cache is stable even when a codec's bytes are not bit-reproducible."""

    renderer: str = "mock"
    profiles: tuple = ()               # export profile names, e.g. ("reel_9x16",)

    def run(self, ctx):
        timeline = ctx.value("timeline")
        out_dir = ctx.stage_dir(self.name)
        suffix = ".mp4" if self.renderer == "ffmpeg" else ".avi"
        master_path = out_dir / f"master{suffix}"
        meta = timeline.meta
        cfg = ReelEngineConfig(render=RenderConfig(
            width=meta.width, height=meta.height, fps=meta.fps, renderer=self.renderer))
        result = get_renderer(self.renderer, cfg).render(RenderRequest(
            timeline=timeline, output_path=master_path, renderer=self.renderer,
            export_profiles=tuple(self.profiles)))
        exports = [{"profile": e.profile, "path": str(e.path), "width": e.width,
                    "height": e.height, "aspect": e.aspect} for e in result.exports]
        content = hash_json({"renderer": self.renderer,
                             "timeline_hash": result.timeline_hash or timeline_content_hash(timeline),
                             "profiles": sorted(self.profiles)})
        art = Artifact("master", KIND_FILE, content, value=master_path,
                       path=master_path,
                       meta={"renderer": self.renderer,
                             "width": result.width, "height": result.height,
                             "fps": result.fps, "duration_s": round(result.duration_s, 3),
                             "n_scenes": result.n_scenes,
                             "timeline_hash": result.timeline_hash,
                             "exports": exports})
        return self._single(art)


# -------------------------------------------------------------------------- 10
@dataclass(frozen=True)
class ExportStage(WorkflowStage):
    """Validate + package the platform renditions the renderer produced.

    The renderer emits the master and its export profiles in one pass (Render
    stage); this delivery stage verifies each rendition exists, probes it with the
    existing ``probe_media`` API when ffprobe is present, and packages the set as a
    content-addressed fileset artifact."""

    def run(self, ctx):
        master = ctx.artifact("master")
        export_descs = master.meta.get("exports", [])
        paths: list[Path] = []
        probed: list[dict] = []
        can_probe = ffprobe_available()
        for desc in export_descs:
            p = Path(desc["path"])
            entry = dict(desc)
            entry["exists"] = p.exists()
            if p.exists() and can_probe:
                try:
                    m = probe_media(p)
                    entry["probed"] = {"duration_s": round(m.duration_s, 3),
                                       "width": m.width, "height": m.height,
                                       "readable": m.readable}
                except Exception as exc:  # noqa: BLE001 - probe is best-effort
                    entry["probe_error"] = str(exc)
            if p.exists():
                paths.append(p)
            probed.append(entry)
        files = tuple(paths)
        content = hash_json({"master": master.content_hash,
                             "profiles": sorted(d["profile"] for d in export_descs)})
        art = Artifact("exports", KIND_FILESET, content, value=files,
                       meta={"n_exports": len(files), "profiles": probed,
                             "probed": can_probe})
        return self._single(art)
