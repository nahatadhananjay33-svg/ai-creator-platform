"""Identity consistency metric (optional backend).

Measures face-embedding cosine similarity between the source portrait and
frames sampled across the generated video — the primary objective identity
metric. Also reports drift (first-third vs last-third similarity), the
long-video failure mode diffusion models exhibit.

Backend: InsightFace (ArcFace embeddings), ``pip install .[face-id]``.
NOTE: InsightFace's bundled models are research-only; this is fine for
benchmarking on a research machine but the production identity check in
Phase A4 must swap to a commercially licensed embedder behind this same
class (same pattern as the voice engine's speaker-similarity metric).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from foundation.exceptions import MetricUnavailableError
from foundation.logging import get_logger

logger = get_logger("avatar_engine.evaluation.identity")

#: Frames sampled per video for identity checks.
SAMPLE_FRAMES = 12


@dataclass(frozen=True)
class IdentityResult:
    """Identity similarity in [0, 1] plus drift across the video."""

    mean_similarity: float
    drift: float  # first-third mean minus last-third mean (positive = decaying)
    frames_with_face: int
    frames_sampled: int


class IdentityConsistencyMetric:
    """ArcFace-based identity similarity between source image and video frames."""

    def __init__(self) -> None:
        self._app = None

    @property
    def available(self) -> bool:
        try:
            import insightface  # type: ignore[import-not-found]  # noqa: F401
            import cv2  # type: ignore[import-not-found]  # noqa: F401

            return True
        except ImportError:
            return False

    def _ensure_app(self):  # noqa: ANN202 - backend type is optional
        if self._app is None:
            try:
                import insightface  # type: ignore[import-not-found]
            except ImportError as exc:
                raise MetricUnavailableError(
                    "Identity metric requires insightface: pip install .[face-id]",
                    metric="identity_similarity",
                ) from exc
            self._app = insightface.app.FaceAnalysis(name="buffalo_l")
            self._app.prepare(ctx_id=-1, det_size=(640, 640))
        return self._app

    def _embed(self, image) -> "object | None":  # noqa: ANN001 - numpy optional
        faces = self._ensure_app().get(image)
        if not faces:
            return None
        # Largest detected face is the subject.
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return face.normed_embedding

    def compare(self, source_image: Path, video_path: Path) -> IdentityResult:
        """Raises :class:`MetricUnavailableError` when backends are missing."""
        try:
            import cv2  # type: ignore[import-not-found]
            import numpy as np  # type: ignore[import-not-found]
        except ImportError as exc:
            raise MetricUnavailableError(
                "Identity metric requires opencv+numpy: pip install .[video]",
                metric="identity_similarity",
            ) from exc

        source = cv2.imread(str(source_image))
        if source is None:
            raise MetricUnavailableError(
                f"Cannot read source image {source_image}", metric="identity_similarity"
            )
        ref = self._embed(source)
        if ref is None:
            raise MetricUnavailableError(
                "No face detected in source image", metric="identity_similarity"
            )

        cap = cv2.VideoCapture(str(video_path))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
        indices = [int(i * (total - 1) / max(1, SAMPLE_FRAMES - 1)) for i in range(SAMPLE_FRAMES)]
        sims: list[float] = []
        try:
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok:
                    continue
                emb = self._embed(frame)
                if emb is None:
                    continue
                sims.append(float(np.clip(np.dot(ref, emb), 0.0, 1.0)))
        finally:
            cap.release()

        if not sims:
            raise MetricUnavailableError(
                "No faces detected in any sampled video frame", metric="identity_similarity"
            )
        third = max(1, len(sims) // 3)
        drift = (sum(sims[:third]) / third) - (sum(sims[-third:]) / third)
        return IdentityResult(
            mean_similarity=round(sum(sims) / len(sims), 4),
            drift=round(drift, 4),
            frames_with_face=len(sims),
            frames_sampled=len(indices),
        )
