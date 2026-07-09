"""AI Prompt & Storyboard Engine regression tests (Phase C10).

Fully hermetic and deterministic: uses ONLY the MockProvider — NO API key, NO
network, NO model, NO renderer, NO GPU. Covers the AI-storyboard IR + serde, the
validator, prompt templates, providers (mock + interface conformance of the real
ones), the script seam, and the ScriptEngine facade end to end. Every produced
timeline is run through the shared Timeline validator so an AI brief can never
yield an unrenderable reel.
"""
from __future__ import annotations

import pytest

from reel_engine.timeline.validate import validate_timeline
from scene_engine.storyboard.types import SCENE_TYPES

from script_engine import (
    AIStoryboard,
    ScriptEngine,
    ScriptScene,
    ScriptValidationError,
    get_provider,
    get_template,
    storyboard_from_json,
    storyboard_to_json,
    storyboard_to_script,
    template_names,
    validate_storyboard,
)
from script_engine.config.settings import ScriptEngineConfig
from script_engine.providers import GenerationRequest, PROVIDER_NAMES, StoryboardProvider
from script_engine.providers.base import clean_topic, topic_keywords
from script_engine.storyboard.script import SCENE_MARKER

PROMPT = "Why investing in real estate early is beneficial"


def _mock_storyboard(prompt=PROMPT, template="general", **cfg_over) -> AIStoryboard:
    cfg = ScriptEngineConfig(template=template, **cfg_over)
    req = GenerationRequest.build(prompt, get_template(template), cfg)
    return get_provider("mock").generate(req)


# --------------------------------------------------------------- storyboard IR
def test_storyboard_shape_and_derived_props():
    sb = _mock_storyboard()
    assert isinstance(sb, AIStoryboard) and sb.n_scenes > 0
    assert sb.provider == "mock" and sb.template == "general"
    assert sb.word_count == sum(s.word_count for s in sb.scenes)
    assert sb.scenes[0].scene_type == "hook" and sb.scenes[-1].cta
    assert sb.hook == sb.scenes[0].narration


def test_storyboard_is_immutable():
    sb = _mock_storyboard()
    with pytest.raises(Exception):
        sb.scenes[0].narration = "x"          # frozen dataclass


def test_serde_round_trip():
    sb = _mock_storyboard(template="finance")
    rebuilt = storyboard_from_json(storyboard_to_json(sb))
    assert rebuilt.scenes == sb.scenes and rebuilt.title == sb.title
    assert rebuilt.provider == sb.provider


# ---------------------------------------------------------------- validation
def test_valid_storyboard_has_no_problems():
    assert validate_storyboard(_mock_storyboard()) == []


def test_validator_flags_empty_and_unsupported_and_duplicates():
    bad = AIStoryboard(title="", scenes=(
        ScriptScene("", "nonsense_type"),
        ScriptScene("Same line here.", "hook"),
        ScriptScene("Same line here.", "hook"),
    ))
    problems = validate_storyboard(bad, min_scenes=2, max_scenes=8)
    assert any("title" in p for p in problems)
    assert any("empty narration" in p for p in problems)
    assert any("unsupported scene_type" in p for p in problems)
    assert any("duplicate scene" in p for p in problems)


def test_validator_flags_scene_count_bounds():
    sb = _mock_storyboard()
    assert any("too few" in p for p in validate_storyboard(sb, min_scenes=99))
    assert any("too many" in p for p in validate_storyboard(sb, max_scenes=1))


def test_validate_or_raise():
    from script_engine.validator import validate_or_raise
    with pytest.raises(ScriptValidationError):
        validate_or_raise(AIStoryboard(title="t", scenes=()))


# ----------------------------------------------------------------- templates
def test_all_templates_load_and_produce_valid_storyboards():
    assert set(template_names()) == {
        "general", "real_estate", "finance", "medical", "education", "news",
        "motivational", "talking_head"}
    for name in template_names():
        sb = _mock_storyboard(template=name, max_scenes=8)
        assert validate_storyboard(sb, min_scenes=3, max_scenes=8) == [], name
        assert sb.tone and sb.target_audience                    # framing carried through


def test_unknown_template_falls_back_to_general():
    assert get_template("does_not_exist").name == "general"


# ----------------------------------------------------------------- providers
def test_mock_provider_is_deterministic():
    a, b = _mock_storyboard(template="education"), _mock_storyboard(template="education")
    assert storyboard_to_json(a) == storyboard_to_json(b)


def test_mock_scene_count_clamped_and_capped():
    # target 40s -> ~8 scenes, but talking_head has few body lines -> capped, no dup
    sb = _mock_storyboard(template="talking_head", target_duration_s=200.0, max_scenes=20)
    assert sb.n_scenes <= 2 + len(get_template("talking_head").body)
    narrations = [s.narration for s in sb.scenes]
    assert len(narrations) == len(set(narrations))               # no duplicate lines
    # min_scenes floor honoured
    assert _mock_storyboard(target_duration_s=1.0, min_scenes=3).n_scenes >= 3


def test_mock_scene_types_are_supported():
    sb = _mock_storyboard(template="news")
    assert all(s.scene_type in SCENE_TYPES for s in sb.scenes)


def test_topic_extraction_and_keywords():
    assert clean_topic("Why compound interest matters") == "compound interest matters"
    assert clean_topic("Make a reel about space travel.") == "space travel"
    assert "compound" in topic_keywords("compound interest and savings")


def test_all_providers_conform_to_interface():
    assert set(PROVIDER_NAMES) == {"mock", "openai", "anthropic", "gemini"}
    for name in PROVIDER_NAMES:
        assert isinstance(get_provider(name), StoryboardProvider), name


def test_anthropic_provider_defaults():
    from script_engine.providers.anthropic_provider import AnthropicProvider, DEFAULT_MODEL
    assert DEFAULT_MODEL == "claude-opus-4-8"                    # latest Opus
    assert AnthropicProvider().name == "anthropic"


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        get_provider("nope")


# ------------------------------------------------------------------- script
def test_to_script_uses_scene_markers():
    sb = _mock_storyboard()
    script = storyboard_to_script(sb)
    assert script.count(SCENE_MARKER) == sb.n_scenes - 1
    assert sb.scenes[0].narration in script


# ------------------------------------------------------------------- facade
def test_facade_prompt_to_timeline_end_to_end():
    engine = ScriptEngine()
    ai_sb, scene_sb, tl = engine.plan_timeline(PROMPT, template="real_estate")
    assert ai_sb.provider == "mock" and ai_sb.n_scenes > 0
    assert scene_sb.n_scenes > 0 and scene_sb.duration_s > 0
    assert tl.n_scenes == scene_sb.n_scenes and tl.has_captions
    assert validate_timeline(tl) == []                           # renderer invariants hold


def test_facade_is_deterministic():
    a = ScriptEngine().generate_storyboard(PROMPT, template="finance")
    b = ScriptEngine().generate_storyboard(PROMPT, template="finance")
    assert storyboard_to_json(a) == storyboard_to_json(b)


def test_facade_validates_and_raises_on_bad_provider_output():
    class _BadProvider:
        name = "bad"

        def generate(self, request):
            return AIStoryboard(title="t", scenes=(ScriptScene("", "hook"),))

    engine = ScriptEngine(provider=_BadProvider())
    with pytest.raises(ScriptValidationError):
        engine.generate_storyboard(PROMPT)


def test_facade_template_and_provider_override():
    engine = ScriptEngine(ScriptEngineConfig(template="general", provider="mock"))
    sb = engine.generate_storyboard(PROMPT, template="medical", provider="mock")
    assert sb.template == "medical"


def test_config_defaults_and_validation():
    from script_engine import load_script_engine_config
    cfg = load_script_engine_config()
    assert cfg.provider == "mock" and cfg.min_scenes == 3 and cfg.max_scenes == 8
    with pytest.raises(ValueError):
        ScriptEngineConfig(min_scenes=5, max_scenes=3)
    with pytest.raises(ValueError):
        ScriptEngineConfig(temperature=3.0)


def test_config_env_override(monkeypatch):
    from script_engine import load_script_engine_config
    monkeypatch.setenv("AICP__script__template", "news")
    assert load_script_engine_config().template == "news"
