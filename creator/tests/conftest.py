"""Shared hermetic fixtures for the creator (Version 1.0) tests.

Everything is single-user and deterministic: the end-to-end test runs the whole
prompt -> reel -> quality -> metadata flow with the ``mock`` renderer into
pytest's ``tmp_path`` — no GPU, no FFmpeg, no network, no APIs.
"""
from __future__ import annotations

import pytest

from creator.config import CreatorConfig


@pytest.fixture
def base_config(tmp_path) -> CreatorConfig:
    """A minimal, hermetic config writing into an isolated workspace."""
    return CreatorConfig(
        prompt="A quick reel about saving money",
        template="finance",
        renderer="mock",
        profiles=("reel_9x16",),
        language="en",
        creator="Test Creator",
        channel="@test",
        quality_gate=True,
        workspace_root=str(tmp_path / "workspace"),
    )
