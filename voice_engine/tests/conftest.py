"""Shared Voice Engine test fixtures (Phase C17).

The process-global adapter cache (Phase C17 model-reuse optimization) deliberately
keeps loaded adapters alive across ``VoiceEngine`` instances. That is correct at
runtime, but tests must stay isolated — so clear the cache before every test.
"""
from __future__ import annotations

import pytest

from voice_engine.adapters import clear_adapter_cache


@pytest.fixture(autouse=True)
def _isolate_adapter_cache():
    clear_adapter_cache()
    yield
    clear_adapter_cache()
