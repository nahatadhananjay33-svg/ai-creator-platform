"""Analysis + detection (Steps 3 & 5), all hermetic and deterministic."""
from __future__ import annotations

from dataclasses import astuple

from production.voice_dataset.analyze import analyze, load_wav
from production.voice_dataset.config import Config

CFG = Config()


def test_clean_speech(synth, tmp_path):
    p = synth.write_wav(tmp_path / "clean.wav", synth.bursts(150, 20))
    meta, det = analyze(p, CFG)
    assert det.has_speech is True
    assert det.multi_speaker is False
    assert det.has_music is False
    assert det.snr_db >= CFG.snr_good
    assert 18.0 <= meta.duration <= 22.0
    assert meta.speech_duration > 3.0
    assert meta.sample_rate == synth.SR


def test_silence_has_no_speech(synth, tmp_path):
    p = synth.write_wav(tmp_path / "sil.wav", synth.silence(5))
    meta, det = analyze(p, CFG)
    assert det.has_speech is False
    assert meta.speech_duration == 0.0
    assert meta.silence_pct > 0.9


def test_two_speakers_flagged(synth, tmp_path):
    p = synth.write_wav(tmp_path / "two.wav", synth.two_speakers(30))
    _, det = analyze(p, CFG)
    assert det.multi_speaker is True


def test_noisy_low_snr(synth, tmp_path):
    p = synth.write_wav(tmp_path / "noisy.wav", synth.noisy())
    _, det = analyze(p, CFG)
    assert det.snr_db < CFG.snr_fair


def test_deterministic(synth, tmp_path):
    p = synth.write_wav(tmp_path / "d.wav", synth.bursts(150, 10))
    a1 = analyze(p, CFG)
    a2 = analyze(p, CFG)
    assert astuple(a1[0]) == astuple(a2[0])
    assert astuple(a1[1]) == astuple(a2[1])


def test_decodes_stereo_and_widths(synth, tmp_path):
    for width in (1, 2, 4):
        for ch in (1, 2):
            p = synth.write_wav(tmp_path / f"w{width}c{ch}.wav", synth.bursts(150, 4),
                                channels=ch, sampwidth=width)
            data, sr, channels, sw = load_wav(p)
            assert sr == synth.SR and channels == ch and sw == width
            assert data.ndim == 1 and data.size > 0
