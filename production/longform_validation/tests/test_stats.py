"""Statistics, inspection sampling, comparison metrics, A/B/C recommendation."""
from __future__ import annotations

from production.longform_validation.config import V2Config
from production.longform_validation.stats import (
    RECOMMENDATIONS, dataset_metrics, dataset_stats, format_comparison,
    format_inspection, format_recommendation, format_stats, recommend,
    sample_inspection, suitability)

CFG = V2Config()


def rec(fn, accepted=True, quality="excellent", snr=28.0, dur=60.0,
        speech=50.0, reason="accepted"):
    return {"filename": fn, "accepted": accepted, "quality": quality,
            "snr_db": snr, "duration": dur, "speech_duration": speech,
            "reason": reason}


def _records(n_acc=10, n_rej=5, speech=360.0, **kw):
    acc = [rec(f"a{i:03}.wav", True, speech=speech, **kw) for i in range(n_acc)]
    rej = [rec(f"r{i:03}.wav", False, quality="poor", snr=5.0,
               reason="multiple speakers") for i in range(n_rej)]
    return acc + rej


def test_dataset_stats_counts_and_reasons():
    s = dataset_stats(_records(), total_videos=12)
    assert s["total_videos"] == 12 and s["total_clips"] == 15
    assert s["accepted_clips"] == 10 and s["rejected_clips"] == 5
    assert s["accepted_speech_hours"] == 1.0     # 10 * 360 s
    assert s["average_quality"] == "excellent"
    assert s["top_rejection_reasons"][0] == ("multiple speakers", 5)
    text = format_stats(s, "X")
    assert "Accepted speech hours : 1.000" in text


def test_sample_inspection_deterministic_and_capped():
    records = _records(n_acc=40, n_rej=3)
    a1, r1 = sample_inspection(records, 30, seed=7)
    a2, r2 = sample_inspection(records, 30, seed=7)
    assert [x["filename"] for x in a1] == [x["filename"] for x in a2]
    assert len(a1) == 30 and len(r1) == 3        # capped at available rejects
    assert all(x["accepted"] for x in a1) and not any(x["accepted"] for x in r1)
    text = format_inspection(a1, "ACCEPTED")
    assert "ACCEPTED sample (30 clips)" in text


def test_metrics_and_suitability_bands():
    m = dataset_metrics(_records(n_acc=12, speech=360.0))  # 1.2 h accepted speech
    assert m["accepted_speech_hours"] == 1.2
    assert m["avg_snr_db"] == 28.0 and m["quality_score"] == 3.0
    assert suitability(m, CFG) == "suitable on its own"

    m_small = dataset_metrics(_records(n_acc=4, speech=360.0))  # 0.4 h
    assert suitability(m_small, CFG) == "usable as a contribution"

    m_empty = dataset_metrics([rec("r.wav", accepted=False)])
    assert m_empty["accepted_clips"] == 0
    assert suitability(m_empty, CFG) == "not suitable"


def test_recommend_a_b_c_branches():
    big = dataset_metrics(_records(n_acc=12, speech=360.0))       # 1.2 h, high SNR
    mid = dataset_metrics(_records(n_acc=4, speech=360.0))        # 0.4 h
    tiny = dataset_metrics(_records(n_acc=1, speech=100.0))       # 0.028 h
    bad = dataset_metrics(_records(n_acc=2, quality="poor", snr=8.0))
    base = dataset_metrics(_records(n_acc=2, speech=135.0))

    assert recommend(big, base, CFG)[0] == "A"
    assert recommend(mid, base, CFG)[0] == "B"
    assert recommend(tiny, base, CFG)[0] == "B"   # tiny but clean -> supplement
    assert recommend(bad, base, CFG)[0] == "C"

    letter, reasons = recommend(big, base, CFG)
    text = format_recommendation(letter, reasons)
    assert RECOMMENDATIONS["A"] in text and "accepted speech" in reasons[0]


def test_format_comparison_lists_both_datasets():
    yt = dataset_metrics(_records(n_acc=4))
    base = dataset_metrics(_records(n_acc=2))
    text = format_comparison(yt, base, CFG)
    assert "Raw Video Dataset" in text and "YouTube Long-form" in text
    assert "Average SNR (dB)" in text and "suitability" in text
