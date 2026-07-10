"""QualityChecker end-to-end tests over a rendered mock reel (Phase C16)."""
from __future__ import annotations

from quality_engine.checker.config import QualityConfig
from quality_engine.checker.engine import QualityChecker, check_reel
from quality_engine.checker.report import CheckStatus


def test_rendered_reel_passes_with_only_music_warning(reel_artifacts):
    report = QualityChecker().check(reel_artifacts)
    assert report.ok and report.overall is CheckStatus.PASS
    # the built timeline has captions+branding+voice+avatar but no music bed
    assert {c.key for c in report.warnings} == {"music_present"}
    statuses = {c.key: c.status for c in report.checks}
    assert statuses["video_exists"] is CheckStatus.PASS
    assert statuses["audio_matches_video"] is CheckStatus.PASS
    assert statuses["captions_present"] is CheckStatus.PASS
    assert statuses["branding_present"] is CheckStatus.PASS
    assert statuses["resolution_correct"] is CheckStatus.PASS
    assert statuses["duration_within_limits"] is CheckStatus.PASS


def test_report_meta_reflects_measured_reel(reel_artifacts):
    report = check_reel(reel_artifacts)
    assert report.meta["renderer"] == "mock"
    assert report.meta["n_exports"] == 2
    assert report.meta["audio_source"] == "sidecar"
    assert report.meta["duration_s"] == 6.0


def test_checker_is_deterministic(reel_artifacts):
    a = QualityChecker().check(reel_artifacts).to_dict()
    b = QualityChecker().check(reel_artifacts).to_dict()
    assert a == b


def test_tight_duration_limit_fails_the_gate(reel_artifacts):
    report = QualityChecker(QualityConfig(min_duration_s=0.0,
                                          max_duration_s=2.0)).check(reel_artifacts)
    assert not report.ok
    assert [c.key for c in report.failures] == ["duration_within_limits"]


def test_render_text_is_printable(reel_artifacts):
    text = QualityChecker().check(reel_artifacts).render_text()
    assert text.startswith("QUALITY REPORT")
    assert "Overall: PASS" in text
