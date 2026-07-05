"""Tests for the research catalog and profile schema."""
from __future__ import annotations

import pytest

from avatar_engine.reporting.research_report import compute_awards, production_readiness_score
from avatar_engine.research import (
    AvatarTask,
    all_profiles,
    commercial_ready_profiles,
    get_profile,
    production_candidates,
    profiles_by_task,
)


def test_catalog_is_populated_and_sorted() -> None:
    profiles = all_profiles()
    assert len(profiles) >= 12
    assert [p.model_id for p in profiles] == sorted(p.model_id for p in profiles)


def test_profiles_are_internally_consistent() -> None:
    for p in all_profiles():
        assert p.spec.family == "avatar", p.model_id
        assert p.spec.model_id == p.model_id
        for rating in (
            p.ratings.lip_sync, p.ratings.realism, p.ratings.identity_consistency,
            p.ratings.expressiveness, p.ratings.motion_naturalness,
        ):
            assert 1 <= rating <= 5, p.model_id
        assert p.strengths and p.weaknesses, p.model_id
        if not p.production_candidate:
            assert p.excluded_reason, f"{p.model_id} excluded without a reason"


def test_non_commercial_models_are_not_best_production() -> None:
    for p in all_profiles():
        if p.model_id in ("sonic", "float", "wav2lip", "omnihuman"):
            assert not p.spec.license.commercial_use
            assert not p.production_candidate


def test_commercial_ready_subset() -> None:
    ready = {p.model_id for p in commercial_ready_profiles()}
    assert "echomimic-v3" in ready
    assert "musetalk" in ready
    assert "sonic" not in ready
    assert "liveportrait" not in ready  # InsightFace dependency blocks as-shipped use


def test_task_views_and_lookup() -> None:
    lip_sync = {p.model_id for p in profiles_by_task(AvatarTask.VIDEO_LIP_SYNC)}
    assert {"musetalk", "latentsync", "wav2lip"} <= lip_sync
    assert get_profile("sadtalker").display_name == "SadTalker"
    with pytest.raises(KeyError):
        get_profile("does-not-exist")


def test_to_dict_serializes_enums() -> None:
    data = get_profile("echomimic-v3").to_dict()
    assert data["task"] == "audio_driven_body"
    assert data["install_complexity"] == "moderate"
    assert data["ratings"]["overall"] == pytest.approx(4.0)


def test_readiness_score_bounds_and_license_gate() -> None:
    for p in all_profiles():
        score = production_readiness_score(p)
        assert 0.0 <= score <= 1.0, p.model_id
    # A non-commercial model must never outrank the top commercial candidate.
    top_commercial = max(commercial_ready_profiles(), key=production_readiness_score)
    assert production_readiness_score(get_profile("sonic")) < production_readiness_score(
        top_commercial
    )


def test_awards_are_deterministic_and_commercial_where_required() -> None:
    awards = {a.award: a for a in compute_awards()}
    assert set(awards) == {
        "best_lip_sync", "best_realism", "best_identity_consistency",
        "best_lightweight", "best_production_model",
    }
    best_prod = get_profile(awards["best_production_model"].model_id)
    assert best_prod.spec.license.commercial_use
    assert best_prod.production_candidate
    # Awards only go to production candidates.
    for award in awards.values():
        assert get_profile(award.model_id).production_candidate, award.award
