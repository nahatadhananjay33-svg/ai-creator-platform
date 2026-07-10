"""Report value + text-rendering tests (Phase C16)."""
from __future__ import annotations

from quality_engine.checker.report import CheckResult, CheckStatus, QualityReport

P, W, F, S = CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.SKIP


def _r(key, status, detail=""):
    return CheckResult(key=key, label=key.replace("_", " ").title(), status=status, detail=detail)


def test_overall_pass_when_no_failures():
    report = QualityReport(checks=(_r("a", P), _r("b", W, "no music"), _r("c", S)))
    assert report.overall is CheckStatus.PASS
    assert report.ok is True
    assert [c.key for c in report.warnings] == ["b"]
    assert not report.failures


def test_overall_fail_when_any_failure():
    report = QualityReport(checks=(_r("a", P), _r("b", F, "bad")))
    assert report.overall is CheckStatus.FAIL
    assert report.ok is False
    assert [c.key for c in report.failures] == ["b"]


def test_status_counts():
    report = QualityReport(checks=(_r("a", P), _r("b", P), _r("c", W), _r("d", F), _r("e", S)))
    counts = report.status_counts()
    assert counts == {"pass": 2, "warn": 1, "fail": 1, "skip": 1}


def test_render_text_pass_has_no_warnings_section_content():
    report = QualityReport(checks=(_r("video_exists", P), _r("audio", P)))
    text = report.render_text()
    assert "Overall: PASS" in text
    assert "✓ Video Exists" in text
    assert "Warnings\n  None" in text


def test_render_text_lists_warnings_and_marks_failures():
    report = QualityReport(checks=(_r("music", W, "no music"), _r("duration", F, "too long")))
    text = report.render_text()
    assert "Overall: FAIL" in text
    assert "✗ Duration  (too long)" in text
    assert "! Music (no music)" in text  # appears in the Warnings section


def test_to_dict_roundtrips_status_values():
    report = QualityReport(checks=(_r("a", P), _r("b", F)))
    d = report.to_dict()
    assert d["overall"] == "fail" and d["ok"] is False
    assert [c["status"] for c in d["checks"]] == ["pass", "fail"]


def test_check_result_ok_only_false_on_fail():
    assert _r("x", P).ok and _r("x", W).ok and _r("x", S).ok
    assert not _r("x", F).ok


def test_status_marks():
    assert CheckStatus.PASS.mark == "✓"
    assert CheckStatus.FAIL.mark == "✗"
    assert CheckStatus.WARN.mark == "!"
    assert CheckStatus.SKIP.mark == "-"
