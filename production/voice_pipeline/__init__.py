"""Colab orchestration glue for the Voice Dataset Builder.

Thin layer that feeds a flat folder of raw videos (e.g. a mounted Google Drive
folder) into the EXISTING Voice Dataset Builder — it reuses that builder's
extract/analyze/classify/score/decide/storage untouched and only adds:
folder discovery, tqdm progress, resume (skip already-processed clips), Drive
sync of outputs, and a consolidated summary.

Nothing here rewrites the Media Acquisition or Voice Dataset Builder modules.
"""
from .glue import FolderProvider, format_report, run_pipeline

__all__ = ["FolderProvider", "run_pipeline", "format_report"]
