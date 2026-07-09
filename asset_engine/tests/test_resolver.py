"""Asset resolver / catalog / providers / ranking tests (Phase C9).

Fully hermetic and deterministic: NO renderer, NO ffmpeg, NO GPU, NO AI, NO
network. Covers the catalog index, candidate providers (incl. the not-yet-
implemented future stubs), deterministic ranking, the query builder, the resolver
pipeline, and the AssetEngine.resolve_slots facade. Every resolved track is run
through the Timeline validator so retrieval can never emit an unrenderable track.
"""
from __future__ import annotations

import json

import pytest

from reel_engine.interfaces.types import Scene, Timeline
from reel_engine.timeline.validate import validate_timeline

from asset_engine import (
    AssetCatalog,
    AssetEngine,
    AssetQuery,
    AssetResolutionError,
    AssetResolver,
    CatalogEntry,
    FileSystemProvider,
    LocalLibraryProvider,
    MockProvider,
    ProviderManager,
    RankWeights,
    rank_candidates,
)
from asset_engine.catalog.index import tokenize_tags
from asset_engine.providers.candidate import CandidateProvider
from asset_engine.providers.future import (
    AIImageProvider,
    AIVideoProvider,
    StockMediaProvider,
)
from asset_engine.providers.placeholder import generate_image
from asset_engine.ranking.scorer import score_candidate
from asset_engine.resolver.query import build_query, region_of


class _Slot:
    """Minimal structural AssetSlot stand-in."""

    def __init__(self, slot_id, kind, hint="", layout="full_screen",
                 start_s=0.0, end_s=3.0, z_index=0, required=True):
        self.slot_id, self.kind, self.hint, self.layout = slot_id, kind, hint, layout
        self.start_s, self.end_s, self.z_index, self.required = start_s, end_s, z_index, required

    @property
    def duration_s(self):
        return self.end_s - self.start_s


def _entries():
    return [
        CatalogEntry("charts/growth.png", "/lib/charts/growth.png", "chart",
                     ("growth", "revenue"), 1080, 1920),
        CatalogEntry("charts/generic.png", "/lib/charts/generic.png", "chart",
                     (), 640, 360),
        CatalogEntry("images/city.png", "/lib/images/city.png", "image",
                     ("city", "skyline"), 1080, 1920),
        CatalogEntry("videos/launch.mp4", "/lib/videos/launch.mp4", "video",
                     ("launch", "rocket"), 1920, 1080, 6.0),
    ]


# ------------------------------------------------------------------- catalog
def test_catalog_from_entries_and_search_by_family():
    cat = AssetCatalog.from_entries(_entries())
    assert cat.size == 4 and "chart" in cat.kinds()
    charts = cat.search(kind="chart")            # image family: 3 image-like entries
    assert {e.entry_id for e in charts} == {
        "charts/growth.png", "charts/generic.png", "images/city.png"}
    vids = cat.search(kind="video")
    assert [e.entry_id for e in vids] == ["videos/launch.mp4"]
    # stable order (sorted by entry_id)
    assert charts == sorted(charts, key=lambda e: e.entry_id)


def test_catalog_from_directory_infers_kind_and_tags(tmp_path):
    generate_image(tmp_path / "charts" / "retention_growth.png", width=1280, height=720)
    generate_image(tmp_path / "icons" / "arrow_up.png", width=64, height=64)
    cat = AssetCatalog.from_directory(tmp_path)
    by_id = {e.entry_id: e for e in cat.entries}
    assert by_id["charts/retention_growth.png"].kind == "chart"
    assert by_id["charts/retention_growth.png"].tags == ("retention", "growth")
    assert by_id["charts/retention_growth.png"].width == 1280
    assert by_id["icons/arrow_up.png"].kind == "icon"


def test_catalog_from_manifest(tmp_path):
    mani = tmp_path / "m.json"
    mani.write_text(json.dumps([
        {"path": "/x/a.mp4", "kind": "video", "tags": ["launch"],
         "width": 1920, "height": 1080, "duration_s": 5.0}]))
    cat = AssetCatalog.from_manifest(mani)
    assert cat.size == 1 and cat.entries[0].kind == "video"
    assert cat.entries[0].duration_s == 5.0


def test_tokenize_tags_drops_stopwords_and_kinds():
    assert tokenize_tags("chart: retention over the growth") == ("retention", "over", "growth")
    assert tokenize_tags("image of a city skyline") == ("city", "skyline")


def test_candidate_and_entry_derived_props():
    e = _entries()[3]
    c = e.to_candidate("local_library")
    assert c.candidate_id == "local_library:videos/launch.mp4"
    assert c.is_video and c.aspect_ratio == pytest.approx(1920 / 1080)
    assert c.pixels == 1920 * 1080 and c.family == "video"


# ----------------------------------------------------------------- providers
def test_local_library_provider_returns_family_candidates():
    lib = LocalLibraryProvider(AssetCatalog.from_entries(_entries()))
    cands = lib.search(AssetQuery(kind="chart"))
    assert all(c.family == "image" for c in cands) and len(cands) == 3
    assert all(c.provider == "local_library" for c in cands)


def test_filesystem_provider_scans_directory(tmp_path):
    generate_image(tmp_path / "images" / "a_photo.png", width=800, height=600)
    fs = FileSystemProvider(tmp_path)
    cands = fs.search(AssetQuery(kind="image"))
    assert len(cands) == 1 and cands[0].provider == "filesystem"


def test_mock_provider_is_deterministic_and_typed():
    q = AssetQuery(kind="chart", tags=("growth",))
    a = MockProvider(n=3).search(q)
    b = MockProvider(n=3).search(q)
    assert [c.candidate_id for c in a] == [c.candidate_id for c in b]
    assert a[0].kind == "chart" and a[1].kind == "image"     # first exact, rest family


def test_providers_satisfy_protocol():
    assert isinstance(LocalLibraryProvider(AssetCatalog()), CandidateProvider)
    assert isinstance(MockProvider(), CandidateProvider)


@pytest.mark.parametrize("Provider", [StockMediaProvider, AIImageProvider, AIVideoProvider])
def test_future_providers_are_not_implemented(Provider):
    assert isinstance(Provider(), CandidateProvider)          # same interface...
    with pytest.raises(NotImplementedError):                  # ...but not implemented
        Provider().search(AssetQuery(kind="image"))


# ------------------------------------------------------------------- ranking
def test_exact_kind_and_tag_match_wins():
    cat = AssetCatalog.from_entries(_entries())
    q = AssetQuery(kind="chart", tags=("growth",), target_aspect=1080 / 1920,
                   min_width=1080, min_height=1920)
    ranked = rank_candidates(LocalLibraryProvider(cat).search(q), q, RankWeights())
    assert ranked[0].candidate.candidate_id == "local_library:charts/growth.png"
    assert ranked[0].rank == 0 and ranked[0].score > ranked[1].score


def test_ranking_is_deterministic_with_stable_tiebreak():
    cat = AssetCatalog.from_entries(_entries())
    q = AssetQuery(kind="image")
    r1 = rank_candidates(LocalLibraryProvider(cat).search(q), q, RankWeights())
    r2 = rank_candidates(LocalLibraryProvider(cat).search(q), q, RankWeights())
    assert [r.candidate.candidate_id for r in r1] == [r.candidate.candidate_id for r in r2]


def test_type_score_never_crosses_still_video_divide():
    still = CatalogEntry("i", "/x/i.png", "image", (), 1920, 1080).to_candidate("p")
    vid_q = AssetQuery(kind="video", target_duration_s=3.0)
    assert score_candidate(still, vid_q).breakdown.type == 0.0


def test_resolution_and_aspect_components():
    small = CatalogEntry("s", "/x/s.png", "chart", (), 320, 180).to_candidate("p")
    q = AssetQuery(kind="chart", target_aspect=16 / 9, min_width=1920, min_height=1080)
    b = score_candidate(small, q).breakdown
    assert b.aspect == pytest.approx(1.0)          # 16:9 matches
    assert b.resolution < 1.0                       # too few pixels


# ------------------------------------------------------------------- query
def test_build_query_from_slot():
    slot = _Slot("s0", "chart", hint="chart: retention over time",
                 layout="full_screen", end_s=4.0)
    q = build_query(slot, frame_width=1080, frame_height=1920)
    assert q.kind == "chart" and "retention" in q.tags
    assert q.target_aspect == pytest.approx(1080 / 1920)
    assert q.min_width == 1080 and q.min_height == 1920


def test_region_of_pip_is_smaller_than_full():
    full = region_of("full_screen", 1080, 1920)
    pip = region_of("picture_in_picture", 1080, 1920)
    assert pip[0] < full[0] and pip[1] < full[1]


# ------------------------------------------------------------------- resolver
def test_resolver_selects_same_family_only():
    # only a video in the library, but the slot wants a chart -> unsatisfied
    cat = AssetCatalog.from_entries([
        CatalogEntry("v", "/x/v.mp4", "video", (), 1920, 1080, 6.0)])
    resolver = AssetResolver(ProviderManager([LocalLibraryProvider(cat)]))
    res = resolver.resolve_slot(_Slot("s0", "chart"))
    assert not res.satisfied and res.candidate is None


def test_resolver_min_score_rejects_weak_matches():
    cat = AssetCatalog.from_entries(_entries())
    strict = AssetResolver(ProviderManager([LocalLibraryProvider(cat)]), min_score=999.0)
    assert not strict.resolve_slot(_Slot("s0", "chart")).satisfied


def test_manager_dedups_by_path():
    cat = AssetCatalog.from_entries(_entries())
    mgr = ProviderManager([LocalLibraryProvider(cat, name="a"),
                           LocalLibraryProvider(cat, name="b")])
    cands = mgr.candidates(AssetQuery(kind="video"))
    assert len(cands) == 1 and cands[0].provider == "a"        # first provider wins


# ------------------------------------------------------------------- facade
@pytest.fixture
def library(tmp_path):
    generate_image(tmp_path / "charts" / "growth_revenue.png", width=1080, height=1920)
    generate_image(tmp_path / "images" / "city_skyline.png", width=1080, height=1920)
    generate_image(tmp_path / "images" / "rocket_launch.png", width=1080, height=1920)
    return tmp_path


def test_resolve_slots_builds_valid_track(library):
    slots = [_Slot("scene-000-asset-00", "chart", "chart: growth revenue",
                   layout="full_screen"),
             _Slot("scene-001-asset-00", "image", "image: city skyline",
                   layout="picture_in_picture")]
    track, resolutions = AssetEngine().resolve_slots(slots, library_dir=library)
    assert track.n_clips == 2 and all(r.satisfied for r in resolutions)
    # the chosen files are real and the clip ids echo the slots
    assert {c.clip_id for c in track.clips} == {"scene-000-asset-00", "scene-001-asset-00"}
    tl = Timeline(scenes=(Scene.simple(0, (0, 0, 255), "x", duration_s=10.0),),
                  asset_tracks=(track,))
    assert validate_timeline(tl) == []


def test_resolve_slots_strict_raises_on_missing_required(library):
    # a video slot with no video in the (image-only) library -> required, strict
    slots = [_Slot("s0", "video", "video: footage", layout="full_screen")]
    with pytest.raises(AssetResolutionError):
        AssetEngine().resolve_slots(slots, library_dir=library, strict=True)


def test_resolve_slots_non_strict_skips_missing(library):
    slots = [_Slot("s0", "video", "video: footage"),
             _Slot("s1", "chart", "chart: growth revenue")]
    track, res = AssetEngine().resolve_slots(slots, library_dir=library, strict=False)
    assert track.n_clips == 1 and not res[0].satisfied and res[1].satisfied


def test_sided_layout_alternates_halves(library):
    slots = [_Slot("s0", "image", "image: city skyline", layout="side_by_side", z_index=0),
             _Slot("s1", "image", "image: rocket launch", layout="side_by_side", z_index=1)]
    track, _ = AssetEngine().resolve_slots(slots, library_dir=library)
    sides = {c.clip_id: c.layout.side for c in track.clips}
    assert sides["s0"] == "left" and sides["s1"] == "right"


def test_resolve_slots_is_deterministic(library):
    slots = [_Slot("s0", "chart", "chart: growth revenue")]
    t1, _ = AssetEngine().resolve_slots(slots, library_dir=library)
    t2, _ = AssetEngine().resolve_slots(slots, library_dir=library)
    assert [c.source.uri for c in t1.clips] == [c.source.uri for c in t2.clips]
