"""Tests for the Streaming Manager and PCM helpers."""
from __future__ import annotations

import asyncio

import pytest

from foundation.constants import Language
from foundation.model_manager import Device
from foundation.shared_utils import generate_sine_wav
from voice_engine.adapters.mock import MockVoiceAdapter
from voice_engine.interfaces import StreamingTTSEngine, SynthesisRequest
from voice_engine.streaming import StreamingManager, resample, to_mono, wav_to_chunks
from voice_engine.streaming.pcm import resample_pcm_bytes
from voice_engine.tts.config import StreamingConfig


class PlainEngine:
    """Non-streaming engine: only synthesize(), to force the fallback path."""
    def __init__(self) -> None:
        self._inner = MockVoiceAdapter(device=Device.CPU)

    @property
    def engine_id(self) -> str:
        return self._inner.engine_id

    @property
    def capabilities(self):
        return self._inner.capabilities

    def synthesize(self, request: SynthesisRequest):
        return self._inner.synthesize(request)


def _request(text: str = "First sentence. Second sentence.") -> SynthesisRequest:
    return SynthesisRequest(text=text, language=Language.ENGLISH)


def test_native_streaming_passthrough() -> None:
    manager = StreamingManager(StreamingConfig(chunk_ms=100))
    engine = MockVoiceAdapter(device=Device.CPU)
    chunks = list(manager.stream(engine, _request()))
    assert chunks
    assert chunks[-1].is_final
    assert all(c.sample_rate == chunks[0].sample_rate for c in chunks)


def test_native_streaming_resamples_to_telephony_rate() -> None:
    manager = StreamingManager(StreamingConfig(chunk_ms=100, sample_rate=8_000))
    engine = MockVoiceAdapter(device=Device.CPU)
    chunks = list(manager.stream(engine, _request()))
    assert all(c.sample_rate == 8_000 for c in chunks)


def test_fallback_sentence_streaming() -> None:
    manager = StreamingManager(StreamingConfig(chunk_ms=100, sample_rate=16_000))
    engine = PlainEngine()
    assert not isinstance(engine, StreamingTTSEngine)
    chunks = list(manager.stream(engine, _request()))
    assert chunks
    assert chunks[-1].is_final
    assert sum(c.is_final for c in chunks) == 1  # only the very last chunk
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.sample_rate == 16_000 for c in chunks)


def test_astream_matches_sync_stream() -> None:
    manager = StreamingManager(StreamingConfig(chunk_ms=100))
    engine = MockVoiceAdapter(device=Device.CPU)

    async def collect() -> list:
        return [c async for c in manager.astream(engine, _request())]

    async_chunks = asyncio.run(collect())
    sync_chunks = list(manager.stream(engine, _request()))
    assert len(async_chunks) == len(sync_chunks)
    assert async_chunks[-1].is_final


def test_resample_changes_length_proportionally() -> None:
    wav = generate_sine_wav(duration_s=1.0, sample_rate=24_000)
    down = resample(wav, 8_000)
    assert down.sample_rate == 8_000
    assert down.n_frames == pytest.approx(8_000, rel=0.01)
    assert down.duration_s == pytest.approx(1.0, abs=0.01)


def test_resample_pcm_bytes_noop_when_rates_match() -> None:
    payload = b"\x00\x01" * 100
    assert resample_pcm_bytes(payload, 16_000, 16_000) is payload


def test_wav_to_chunks_marks_only_last_final() -> None:
    wav = generate_sine_wav(duration_s=0.5, sample_rate=16_000)
    chunks = wav_to_chunks(wav, chunk_ms=100, start_index=5, final=True)
    assert chunks[0].chunk_index == 5
    assert [c.is_final for c in chunks] == [False] * (len(chunks) - 1) + [True]
    non_final = wav_to_chunks(wav, chunk_ms=100, final=False)
    assert not any(c.is_final for c in non_final)


def test_to_mono_downmixes_stereo() -> None:
    import array

    from foundation.shared_utils import WavData

    stereo = WavData(
        samples=array.array("h", [100, 200, 300, 500]), sample_rate=16_000, channels=2
    )
    mono = to_mono(stereo)
    assert mono.channels == 1
    assert list(mono.samples) == [150, 400]
