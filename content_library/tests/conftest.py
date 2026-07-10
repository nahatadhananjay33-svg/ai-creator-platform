"""Shared fixtures for the Content Library tests (Phase C15).

Everything is hermetic and deterministic: a monotonic counter clock makes every
``created_at`` / ``modified_at`` reproducible, and libraries live under pytest's
tmp_path — no GPU, no APIs, no network.
"""
from __future__ import annotations

import itertools

import pytest

from content_library import ContentLibrary


@pytest.fixture
def clock():
    """A deterministic, strictly increasing ISO clock."""
    counter = itertools.count(1)
    return lambda: f"2026-01-01T00:00:{next(counter):02d}Z"


@pytest.fixture
def library(tmp_path, clock):
    return ContentLibrary(tmp_path / "lib", clock=clock)
