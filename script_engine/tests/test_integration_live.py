"""Live-provider integration tests (Phase C10).

These are the ONLY tests that touch a real LLM API. Each is skipped unless the
matching provider SDK is installed AND its API key is set in the environment, so
the default (hermetic) test run never needs a key or network. They assert that a
real provider emits the SAME structured :class:`AIStoryboard` the MockProvider
does and that it passes validation + flows through the deterministic pipeline.

Run explicitly with keys present, e.g.:
    ANTHROPIC_API_KEY=... pytest script_engine/tests/test_integration_live.py -m integration
"""
from __future__ import annotations

import importlib.util
import os

import pytest

from reel_engine.timeline.validate import validate_timeline

from script_engine import ScriptEngine, validate_storyboard
from script_engine.config.settings import ScriptEngineConfig

pytestmark = pytest.mark.integration

_PROMPT = "Why investing in real estate early is beneficial"

_PROVIDERS = [
    ("anthropic", "anthropic", "ANTHROPIC_API_KEY"),
    ("openai", "openai", "OPENAI_API_KEY"),
    ("gemini", "google.generativeai", "GEMINI_API_KEY"),
]


def _available(module: str, env: str) -> bool:
    return importlib.util.find_spec(module) is not None and bool(os.environ.get(env))


@pytest.mark.parametrize("provider,module,env", _PROVIDERS)
def test_live_provider_emits_valid_storyboard_and_reel(provider, module, env):
    if not _available(module, env):
        pytest.skip(f"{provider}: SDK or {env} not available")
    engine = ScriptEngine(ScriptEngineConfig(provider=provider, template="real_estate"))
    ai_sb, scene_sb, tl = engine.plan_timeline(_PROMPT)
    assert ai_sb.provider == provider and ai_sb.n_scenes > 0
    assert validate_storyboard(ai_sb, min_scenes=1, max_scenes=20) == []
    assert scene_sb.n_scenes > 0 and validate_timeline(tl) == []
