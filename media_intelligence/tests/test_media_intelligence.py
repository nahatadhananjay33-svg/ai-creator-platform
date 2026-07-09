"""Media Intelligence Engine regression tests (Phase C13).

Fully hermetic and deterministic: MockProvider + a synthetic in-memory registry +
the mock renderer — NO API key, NO network, NO model, NO GPU, NO ffmpeg, NO real
files. Covers the registry, deterministic search/ranking, per-scene B-roll
recommendations (confidence + explanations + patches), the media provider seam
(mocks + future stubs), the consistency engine, music/voice recommendation, the
cache, the Creator Studio integration, and the end-to-end
recommend → patch → render loop. The phase invariants are asserted directly:
media decisions are deterministic, replacements are immutable patches, the project
is never mutated, and replay stays byte-identical.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from reel_engine.timeline.validate import validate_timeline

from creator_studio import StudioSession
from editing_engine.patches.operations import MusicPatch, ReplaceAssetPatch
from script_engine import storyboard_to_json

from asset_engine.catalog.types import AssetQuery

from media_intelligence import (
    AssetCache,
    AssetRegistry,
    AssetSearchEngine,
    ConsistencyEngine,
    MediaIntelligenceEngine,
    MediaStudioController,
    MusicRecommender,
    RegisteredAsset,
    VoiceRecommender,
    all_mock_providers,
    cache_key,
    mock_provider_for,
)
from media_intelligence.providers import REAL_PROVIDERS
from media_intelligence.registry import make_asset_id

PROMPT = "Why investing in real estate early is beneficial"


def _asset(uri, kind, tags, meta=None, w=1920, h=1080, dur=0.0, license="cc0"):
    return RegisteredAsset(
        asset_id=make_asset_id(kind, uri, w, h, dur), uri=uri, kind=kind,
        tags=tuple(tags), width=w, height=h, duration_s=dur, source="library",
        license=license, meta=meta or {})


@pytest.fixture
def registry() -> AssetRegistry:
    return AssetRegistry([
        _asset("lib/property_growth.jpg", "image", ("property", "growth", "invest"),
               {"dominant_color": "blue", "style": "flat", "subject": "city"}),
        _asset("lib/city_skyline.mp4", "video", ("city", "skyline", "property"),
               {"dominant_color": "blue", "style": "flat"}, dur=12.0, license="royalty_free"),
        _asset("lib/chart_returns.png", "chart", ("returns", "growth", "numbers", "property"),
               {"dominant_color": "green", "style": "flat"}),
        _asset("lib/keys_home.jpg", "image", ("keys", "home", "buy", "early"),
               {"dominant_color": "red", "style": "photo", "subject": "hands"}, w=1080, h=1080),
    ])


@pytest.fixture
def project():
    return StudioSession.new(PROMPT, template="real_estate").project


@pytest.fixture
def engine(registry):
    return MediaIntelligenceEngine(registry)


# ------------------------------------------------------------------ registry
def test_registry_stable_ids_and_idempotent(registry):
    a = _asset("lib/property_growth.jpg", "image", ("property",))
    b = _asset("lib/property_growth.jpg", "image", ("different", "tags"))
    assert a.asset_id == b.asset_id                          # id is identity, not tags
    size = registry.size
    registry.register(a)                                     # re-register same identity
    assert registry.size == size                             # idempotent


def test_registry_lookup_and_stats(registry):
    assert registry.size == 4
    stats = registry.stats()
    assert stats.n_videos == 1 and stats.n_images == 3       # 2 image + 1 chart (image family)
    assert dict(stats.by_kind) == {"chart": 1, "image": 2, "video": 1}
    assert all(a.asset_id.startswith("asset_") for a in registry.all())
    assert registry.by_family("video")[0].kind == "video"


def test_registry_validate_flags_gaps():
    reg = AssetRegistry([
        _asset("lib/ok.jpg", "image", ("x",), license="cc0"),
        _asset("lib/nolicense.jpg", "image", ("y",), license="unknown"),
        _asset("lib/nodims.jpg", "image", ("z",), w=0, h=0),
        _asset("lib/novideodur.mp4", "video", ("v",), dur=0.0),
    ])
    problems = reg.validate()
    assert any("license unknown" in p for p in problems)
    assert any("missing dimensions" in p for p in problems)
    assert any("no duration" in p for p in problems)


def test_registry_as_provider_is_family_filtered(registry):
    provider = registry.as_provider()
    vids = provider.search(AssetQuery(kind="video"), limit=0)
    assert vids and all(c.kind == "video" for c in vids)


# ------------------------------------------------------------------- search
def test_search_ranks_by_relevance_deterministically(engine):
    hits = engine.search("property growth invest", kind="image", limit=5)
    assert hits[0].asset.uri.endswith("property_growth.jpg")   # best tag+kind match
    scores = [h.score for h in hits]
    assert scores == sorted(scores, reverse=True)              # best-first
    assert all(0.0 <= h.relevance <= 1.0 for h in hits)
    again = engine.search("property growth invest", kind="image", limit=5)
    assert [h.asset.asset_id for h in hits] == [h.asset.asset_id for h in again]


def test_search_respects_family_divide(engine):
    # an image query never returns the video asset as a match
    hits = engine.search("city skyline", kind="image", limit=8)
    assert all(h.asset.kind != "video" for h in hits)
    vids = engine.search("city skyline", kind="video", limit=8)
    assert vids and vids[0].asset.kind == "video"


def test_search_best_returns_top_hit(engine):
    best = engine.best("returns numbers", kind="chart")
    assert best is not None and best.asset.uri.endswith("chart_returns.png")


# --------------------------------------------------------------- recommend
def test_recommend_for_project_covers_every_scene(engine, project):
    recs = engine.recommend_broll(project)
    assert recs.n_scenes == project.n_scenes
    assert all(0.0 <= s.confidence <= 1.0 for s in recs.scenes)
    assert recs.mean_confidence > 0.0


def test_recommendation_becomes_replace_asset_patch(engine, project):
    rec = engine.recommend_scene(project, 2)                  # a chart scene
    patch = rec.to_patch()
    assert isinstance(patch, ReplaceAssetPatch)
    assert patch.index == 2 and patch.asset_type == rec.kind
    assert patch.validate(project) == []                      # a valid, applicable edit


def test_recommendation_explains_and_offers_alternatives(engine, project):
    rec = engine.recommend_scene(project, 0, n_alternatives=2)
    assert rec.has_recommendation and "confidence" in rec.explanation
    assert rec.primary.reasons                                # non-empty rationale
    assert len(rec.alternatives) >= 1
    # alternatives are ranked below the primary
    assert rec.alternatives[0].rank > rec.primary.rank


def test_recommendations_are_deterministic(engine, project):
    a = engine.recommend_broll(project)
    b = engine.recommend_broll(project)
    assert a.patches() == b.patches()
    assert [s.explanation for s in a.scenes] == [s.explanation for s in b.scenes]


def test_media_engine_never_mutates_the_project(engine, project):
    before = storyboard_to_json(project.storyboard)
    engine.plan(project)
    engine.recommend_broll(project)
    assert storyboard_to_json(project.storyboard) == before   # untouched


# --------------------------------------------------------------- providers
def test_mock_providers_are_deterministic():
    q = AssetQuery(kind="image", tags=("property", "growth"))
    p = mock_provider_for("pexels")
    assert [c.candidate_id for c in p.search(q)] == [c.candidate_id for c in p.search(q)]
    assert all(c.provider == "pexels" for c in p.search(q))


def test_generative_mock_flags_synthetic():
    q = AssetQuery(kind="image", tags=("x",))
    gen = mock_provider_for("stability_ai").search(q, limit=1)
    assert gen[0].meta.get("generated") is True


def test_every_future_service_has_a_mock_and_a_stub():
    assert len(all_mock_providers()) == len(REAL_PROVIDERS)
    q = AssetQuery(kind="image")
    for cls in REAL_PROVIDERS.values():
        with pytest.raises(NotImplementedError):
            cls().search(q)


# -------------------------------------------------------------- consistency
def test_consistency_clean_set_scores_full():
    ce = ConsistencyEngine()
    assign = {
        0: _asset("a.jpg", "image", (), {"dominant_color": "blue", "style": "flat"}),
        1: _asset("b.jpg", "image", (), {"dominant_color": "blue", "style": "flat"}),
    }
    report = ce.analyze(assign)
    assert report.consistent and report.consistency_score == 1.0


def test_consistency_flags_fragmented_palette_and_mixed_styles():
    ce = ConsistencyEngine(max_palette=2, max_styles=1)
    assign = {
        0: _asset("a.jpg", "image", (), {"dominant_color": "blue", "style": "flat"}),
        1: _asset("b.jpg", "image", (), {"dominant_color": "red", "style": "photo"}),
        2: _asset("c.jpg", "image", (), {"dominant_color": "green", "style": "3d"}),
    }
    report = ce.analyze(assign)
    dims = {f.dimension for f in report.warnings}
    assert "color" in dims and "style" in dims
    assert report.consistency_score < 1.0


def test_consistency_flags_repeated_person_in_inconsistent_style():
    ce = ConsistencyEngine()
    assign = {
        0: _asset("a.jpg", "image", (), {"subject": "alice", "style": "flat"}),
        1: _asset("b.jpg", "image", (), {"subject": "alice", "style": "photo"}),
    }
    report = ce.analyze(assign)
    subj_warn = [f for f in report.warnings if f.dimension == "subject"]
    assert subj_warn and "alice" in subj_warn[0].message
    assert "alice" in report.recurring_subjects


def test_consistency_flags_foreign_brand(project):
    ce = ConsistencyEngine()
    assign = {0: _asset("a.jpg", "image", (), {"brand": "acme"})}
    report = ce.analyze(assign, project=project)              # project theme != acme
    assert any(f.dimension == "brand" for f in report.warnings)


# ------------------------------------------------------------------- music
def test_music_recommendation_is_deterministic_and_valid(engine, project):
    from music_engine import soundtrack_names
    a = engine.recommend_music(project)
    b = engine.recommend_music(project)
    assert a.soundtrack == b.soundtrack and a.soundtrack in soundtrack_names()
    assert isinstance(a.to_patch(), MusicPatch)
    assert a.to_patch().validate(project) == []


def test_music_maps_tone_to_soundtrack():
    import dataclasses
    from editing_engine.project import ReelProject
    rec = MusicRecommender()
    sb = StudioSession.new(PROMPT, template="real_estate").project.storyboard
    energetic = ReelProject(storyboard=dataclasses.replace(sb, tone="energetic"))
    calm = ReelProject(storyboard=dataclasses.replace(sb, tone="calm"))
    assert rec.recommend_music(energetic).soundtrack == "upbeat"
    # calm favours a low-energy bed (lofi/ambient), never the upbeat one
    assert rec.recommend_music(calm).soundtrack in ("lofi", "ambient")
    assert rec.recommend_music(calm).soundtrack != "upbeat"


# ------------------------------------------------------------------- voice
def test_voice_recommendation_metadata_and_languages():
    rec = VoiceRecommender()
    assert set(rec.languages()) >= {"en", "hi", "hi-en", "bn"}
    import dataclasses
    from editing_engine.project import ReelProject
    sb = StudioSession.new(PROMPT, template="real_estate").project.storyboard
    energetic = ReelProject(storyboard=dataclasses.replace(sb, tone="energetic"))
    v = rec.recommend_voice(energetic, language="en")
    assert v.voice is not None and v.voice.language == "en"
    assert "energetic" in v.voice.styles and v.confidence == 1.0
    # deterministic
    assert rec.recommend_voice(energetic, language="en").voice == v.voice


def test_voice_supports_multiple_languages():
    rec = VoiceRecommender()
    proj = StudioSession.new(PROMPT, template="real_estate").project
    for lang in ("en", "hi", "hi-en", "bn"):
        v = rec.recommend_voice(proj, language=lang)
        assert v.voice is not None and v.voice.language == lang


# -------------------------------------------------------------------- cache
def test_cache_hits_misses_and_reuse():
    cache = AssetCache()
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return 42

    key = cache_key("q", 1)
    assert cache.get_or_compute(key, compute) == 42           # miss + compute
    assert cache.get_or_compute(key, compute) == 42           # hit, no recompute
    assert calls["n"] == 1
    stats = cache.stats()
    assert stats.hits == 1 and stats.misses == 1 and stats.hit_rate == 0.5


def test_engine_cache_reuses_recommendations(engine, project):
    engine.recommend_broll(project)
    before = engine.cache_stats().hits
    engine.recommend_broll(project)                           # identical → cache hit
    assert engine.cache_stats().hits > before


# ------------------------------------------------- creator studio integration
def test_studio_accept_applies_immutable_patch(registry, engine):
    session = StudioSession.new(PROMPT, template="real_estate")
    ctrl = MediaStudioController(session, engine)
    rev = session.revision
    recommended_kind = ctrl.browse(2).kind                    # capture BEFORE applying
    result = ctrl.accept(2)
    assert result.ok and result.patch_op == "replace_asset"
    assert session.revision == rev + 1                        # a real edit happened
    assert session.project.scenes[2].asset_type == recommended_kind
    assert 2 in ctrl.accepted


def test_studio_reject_makes_no_edit(registry, engine):
    session = StudioSession.new(PROMPT, template="real_estate")
    ctrl = MediaStudioController(session, engine)
    rev = session.revision
    result = ctrl.reject(1)
    assert result.ok and session.revision == rev              # no patch, no bump
    assert 1 in ctrl.rejected


def test_studio_accept_music_applies_music_patch(registry, engine):
    session = StudioSession.new(PROMPT, template="real_estate")
    ctrl = MediaStudioController(session, engine)
    result = ctrl.accept_music()
    assert result.ok and result.patch_op == "change_music"
    assert session.project.soundtrack == ctrl.plan().music.soundtrack


def test_studio_cards_track_status(registry, engine):
    session = StudioSession.new(PROMPT, template="real_estate")
    ctrl = MediaStudioController(session, engine)
    ctrl.accept(0)
    ctrl.reject(1)
    cards = {c.scene_index: c.status for c in ctrl.cards()}
    assert cards[0] == "accepted" and cards[1] == "rejected" and cards[2] == "pending"


# ----------------------------------------------------------- end-to-end loop
def test_end_to_end_recommend_replace_render(registry, tmp_path):
    # 1) prompt -> project (Creator Studio session)
    session = StudioSession.new(PROMPT, template="real_estate", workspace=tmp_path)
    engine = MediaIntelligenceEngine(registry)
    ctrl = MediaStudioController(session, engine)
    # 2) deterministic recommendations + search
    plan = ctrl.plan()
    assert plan.recommendations.n_scenes == session.project.n_scenes
    assert engine.search("property growth", kind="image", limit=3)
    # 3) replace assets through immutable patches (accept all + music)
    results = ctrl.accept_all()
    assert all(r.ok for r in results)
    assert session.revision == session.project.n_scenes + 1   # N asset patches + 1 music
    # 4) project-wide consistency maintained
    report = ctrl.consistency()
    assert 0.0 <= report.consistency_score <= 1.0
    # timeline still valid after all media edits
    assert validate_timeline(session.build_timeline()) == []
    # 5) render an updated playable reel via the existing pipeline
    out = tmp_path / "media_updated.avi"
    result = session.export(out, renderer="mock", export_profiles=("reel_9x16",))
    assert out.exists() and result.n_scenes == session.build_timeline().n_scenes
    # replay stays byte-identical (deterministic revisions)
    assert storyboard_to_json(session.replay().storyboard) == \
        storyboard_to_json(session.project.storyboard)


def test_media_patches_are_all_immutable_patch_types(engine, project):
    plan = engine.plan(project)
    patches = plan.patches()
    assert patches and all(isinstance(p, (ReplaceAssetPatch, MusicPatch)) for p in patches)
    # every asset patch validates against the project (safe to apply)
    for p in patches:
        assert p.validate(project) == []
