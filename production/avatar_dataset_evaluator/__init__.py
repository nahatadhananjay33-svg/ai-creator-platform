"""Avatar Dataset Evaluator.

Evaluates whether a folder of raw videos is suitable for building a high-quality
digital avatar — fully local, CPU-only, offline, deterministic. It does NOT
train or download any model and does not touch the Avatar Engine.

Face detection uses OpenCV's bundled Haar cascade classifiers (classical
Viola-Jones — no deep learning, no download, no GPU); every other metric is a
DSP/statistical heuristic over sampled frames. Metrics are estimates, and their
confidence is documented (see AVATAR_DATASET_EVALUATOR.md).

Entry point: ``python -m production.avatar_dataset_evaluator.evaluate``.
"""

__all__ = ["__version__"]
__version__ = "1.0.0"
