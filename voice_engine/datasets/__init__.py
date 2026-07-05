"""Benchmark and evaluation datasets for the Voice Engine.

Text corpora live in ``data/*.yaml`` (one file per language) and are loaded
through :class:`DatasetManager`. The same prompts serve Phase A1 benchmarking
and Phase A2 regression testing — never fork them per use case.
"""

from voice_engine.datasets.schema import PromptCategory, PromptItem, PromptDataset
from voice_engine.datasets.manager import DatasetManager

__all__ = ["PromptCategory", "PromptItem", "PromptDataset", "DatasetManager"]
