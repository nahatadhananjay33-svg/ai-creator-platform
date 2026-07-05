"""Benchmark case types.

Each case = one adapter x one prompt x one scenario, executed by
``foundation.benchmarking.BenchmarkRunner``.
"""
from __future__ import annotations

from pathlib import Path

from foundation.benchmarking import BenchmarkCase, CaseResult, Measurement
from foundation.exceptions import AdapterNotAvailableError
from foundation.shared_utils import Stopwatch, slugify
from foundation.shared_utils.audio_io import WavData, write_wav
from voice_engine.adapters.base import BaseVoiceAdapter
from voice_engine.datasets import PromptItem
from voice_engine.evaluation import SynthesisEvaluator
from voice_engine.interfaces import (
    StreamingTTSEngine,
    SynthesisRequest,
    VoiceProfile,
)


def _require_supported(adapter: BaseVoiceAdapter, prompt: PromptItem) -> None:
    if not adapter.is_available():
        adapter.load()  # raises AdapterDependencyError -> SKIPPED with install hint
    if not adapter.supports_language(prompt.language):
        raise AdapterNotAvailableError(
            f"{adapter.engine_id} does not support {prompt.language.value}",
            engine=adapter.engine_id,
            language=prompt.language.value,
        )


class SynthesisScenarioCase(BenchmarkCase):
    """Batch synthesis: quality, robustness, RTF, resources."""

    def __init__(
        self,
        adapter: BaseVoiceAdapter,
        prompt: PromptItem,
        evaluator: SynthesisEvaluator,
        audio_dir: Path,
        voice: VoiceProfile | None = None,
        repetition: int = 0,
    ) -> None:
        rep_suffix = f"-r{repetition}" if repetition else ""
        super().__init__(
            case_id=f"{adapter.engine_id}-{prompt.item_id}{rep_suffix}",
            subject_id=adapter.engine_id,
            scenario="synthesis",
        )
        self.adapter = adapter
        self.prompt = prompt
        self.evaluator = evaluator
        self.audio_dir = audio_dir
        self.voice = voice

    def execute(self, result: CaseResult) -> None:
        _require_supported(self.adapter, self.prompt)
        output_path = self.audio_dir / f"{slugify(self.case_id)}.wav"
        request = SynthesisRequest(
            text=self.prompt.text,
            language=self.prompt.language,
            voice=self.voice,
            output_path=output_path,
        )
        synthesis = self.adapter.synthesize(request)
        result.artifacts["audio"] = str(synthesis.audio_path)
        result.metadata.update(
            {
                "language": self.prompt.language.value,
                "category": self.prompt.category.value,
                "text_chars": self.prompt.char_count,
            }
        )
        reference = self.voice.reference_audio if self.voice else None
        for measurement in self.evaluator.evaluate(synthesis, self.prompt, reference):
            result.add(measurement)


class StreamingScenarioCase(BenchmarkCase):
    """Streaming synthesis: first-chunk latency, chunk cadence, total time."""

    def __init__(
        self,
        adapter: BaseVoiceAdapter,
        prompt: PromptItem,
        audio_dir: Path,
        voice: VoiceProfile | None = None,
    ) -> None:
        super().__init__(
            case_id=f"{adapter.engine_id}-{prompt.item_id}-stream",
            subject_id=adapter.engine_id,
            scenario="streaming",
        )
        self.adapter = adapter
        self.prompt = prompt
        self.audio_dir = audio_dir
        self.voice = voice

    def execute(self, result: CaseResult) -> None:
        if not isinstance(self.adapter, StreamingTTSEngine):
            raise AdapterNotAvailableError(
                f"{self.adapter.engine_id} has no native streaming interface",
                engine=self.adapter.engine_id,
            )
        _require_supported(self.adapter, self.prompt)
        request = SynthesisRequest(
            text=self.prompt.text, language=self.prompt.language, voice=self.voice
        )
        chunks: list[bytes] = []
        first_chunk_s: float | None = None
        sample_rate = 0
        with Stopwatch() as sw:
            for chunk in self.adapter.stream_synthesize(request):
                if first_chunk_s is None:
                    first_chunk_s = sw.elapsed_s
                sample_rate = chunk.sample_rate
                chunks.append(chunk.pcm_s16le)
        total_s = sw.elapsed_s

        import array

        samples = array.array("h")
        for chunk in chunks:
            samples.frombytes(chunk)
        wav = WavData(samples=samples, sample_rate=sample_rate or 24000)
        audio_path = write_wav(self.audio_dir / f"{slugify(self.case_id)}.wav", wav)

        result.artifacts["audio"] = str(audio_path)
        result.metadata.update(
            {"language": self.prompt.language.value, "chunks": len(chunks)}
        )
        result.add(Measurement("first_chunk_latency_s", round(first_chunk_s or 0.0, 4), "s",
                               higher_is_better=False))
        result.add(Measurement("synthesis_time_s", round(total_s, 4), "s", higher_is_better=False))
        result.add(Measurement("audio_duration_s", round(wav.duration_s, 4), "s"))
        if wav.duration_s > 0:
            result.add(
                Measurement("real_time_factor", round(total_s / wav.duration_s, 4), "x",
                            higher_is_better=False)
            )
