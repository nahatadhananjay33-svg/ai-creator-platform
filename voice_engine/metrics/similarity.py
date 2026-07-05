"""Speaker similarity metric (optional backend).

Measures cosine similarity between speaker embeddings of the reference and
synthesized audio — the primary objective voice-cloning fidelity metric.

Backend: resemblyzer (VoiceEncoder, GE2E embeddings). Install with
``pip install .[similarity]``. Phase A2 may swap in ECAPA-TDNN
(speechbrain) behind the same class without touching callers.
"""
from __future__ import annotations

from pathlib import Path

from foundation.exceptions import MetricUnavailableError
from foundation.logging import get_logger

logger = get_logger("voice_engine.metrics.similarity")


class SpeakerSimilarityMetric:
    """Embedding-based speaker similarity in [0, 1] (higher = more similar).

    Interpretation guidance (GE2E embeddings, empirical):
    - > 0.85: same-speaker level fidelity
    - 0.75-0.85: recognizably the same voice, some drift
    - < 0.75: noticeably different voice
    """

    def __init__(self) -> None:
        self._encoder = None

    @property
    def available(self) -> bool:
        try:
            import resemblyzer  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_encoder(self):  # noqa: ANN202 - backend type is optional
        if self._encoder is None:
            try:
                from resemblyzer import VoiceEncoder  # type: ignore[import-not-found]
            except ImportError as exc:
                raise MetricUnavailableError(
                    "Speaker similarity requires resemblyzer: pip install .[similarity]",
                    metric="speaker_similarity",
                ) from exc
            self._encoder = VoiceEncoder()
        return self._encoder

    def compare(self, reference_wav: Path, synthesized_wav: Path) -> float:
        encoder = self._ensure_encoder()  # raises MetricUnavailableError if backend missing
        from resemblyzer import preprocess_wav  # type: ignore[import-not-found]
        ref_embed = encoder.embed_utterance(preprocess_wav(str(reference_wav)))
        syn_embed = encoder.embed_utterance(preprocess_wav(str(synthesized_wav)))
        dot = float((ref_embed * syn_embed).sum())
        return max(0.0, min(1.0, dot))
