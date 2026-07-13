"""Classify -> score -> decide outcomes (Steps 4, 6, 7)."""
from __future__ import annotations

from production.voice_dataset.analyze import analyze
from production.voice_dataset.classify import classify
from production.voice_dataset.config import Config
from production.voice_dataset.decide import decide
from production.voice_dataset.models import Decision, Platform
from production.voice_dataset.score import score

CFG = Config()


def _run(path, platform=Platform.YOUTUBE):
    meta, det = analyze(path, CFG)
    cl = classify(meta, det, platform, CFG)
    q = score(meta, det, CFG)
    decision, reason = decide(meta, det, cl, q, CFG)
    return cl, q, decision, reason


def test_clean_speech_accepted(synth, tmp_path):
    p = synth.write_wav(tmp_path / "clean.wav", synth.bursts(150, 20))
    cl, q, decision, reason = _run(p)
    assert decision == Decision.ACCEPT
    assert q.rank >= CFG.accept_min_quality_rank


def test_silence_rejected_no_speech(synth, tmp_path):
    p = synth.write_wav(tmp_path / "sil.wav", synth.silence(5))
    _, _, decision, reason = _run(p)
    assert decision == Decision.REJECT
    assert "no speech" in reason


def test_noisy_rejected(synth, tmp_path):
    p = synth.write_wav(tmp_path / "noisy.wav", synth.noisy())
    _, _, decision, reason = _run(p)
    assert decision == Decision.REJECT


def test_two_speakers_rejected(synth, tmp_path):
    p = synth.write_wav(tmp_path / "two.wav", synth.two_speakers(30))
    _, _, decision, reason = _run(p)
    assert decision == Decision.REJECT
    assert "multiple speakers" in reason
