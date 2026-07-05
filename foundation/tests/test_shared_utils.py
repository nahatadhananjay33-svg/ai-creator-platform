"""Tests for foundation.shared_utils and constants."""
from __future__ import annotations

from pathlib import Path

import pytest

from foundation.constants import Language
from foundation.shared_utils import (
    Stopwatch,
    generate_sine_wav,
    probe_hardware,
    read_wav,
    sha256_text,
    short_hash,
    slugify,
    new_run_id,
    split_sentences,
    write_wav,
)


def test_stopwatch_measures_time() -> None:
    with Stopwatch() as sw:
        sum(range(10_000))
    assert sw.elapsed_s >= 0.0


def test_hashing_stable() -> None:
    assert sha256_text("abc") == sha256_text("abc")
    assert len(short_hash("abc")) == 12


def test_slugify() -> None:
    assert slugify("Hello, World! 123") == "hello-world-123"
    assert slugify("   ") == "untitled"


def test_run_id_unique_and_prefixed() -> None:
    a, b = new_run_id("bench"), new_run_id("bench")
    assert a != b
    assert a.startswith("bench-")


def test_wav_roundtrip(tmp_path: Path) -> None:
    wav = generate_sine_wav(duration_s=0.25, sample_rate=16_000)
    assert wav.duration_s == pytest.approx(0.25, abs=0.01)
    path = write_wav(tmp_path / "tone.wav", wav)
    restored = read_wav(path)
    assert restored.sample_rate == 16_000
    assert restored.n_frames == wav.n_frames


def test_language_from_code() -> None:
    assert Language.from_code("hi") is Language.HINDI
    assert Language.from_code("HI-EN") is Language.HINGLISH
    with pytest.raises(ValueError):
        Language.from_code("xx")


def test_split_sentences_latin_and_devanagari() -> None:
    text = "First sentence. Second one! क्या हाल है। Third?"
    assert split_sentences(text) == [
        "First sentence.",
        "Second one!",
        "क्या हाल है।",
        "Third?",
    ]


def test_split_sentences_max_chars_splits_long_sentence() -> None:
    text = "one two three four five six seven eight nine ten"
    chunks = split_sentences(text, max_chars=20)
    assert all(len(c) <= 20 for c in chunks)
    assert " ".join(chunks) == text


def test_split_sentences_empty_and_invalid() -> None:
    assert split_sentences("   ") == []
    with pytest.raises(ValueError):
        split_sentences("abc", max_chars=0)


def test_probe_hardware_smoke() -> None:
    profile = probe_hardware()
    assert profile.os_name
    assert profile.python_version
    d = profile.to_dict()
    assert "gpus" in d
