"""Core model regression tests (Phase C14) — graph, artifacts, codecs, context.

Fully hermetic and deterministic: no engine, no I/O beyond a tmp dir, no GPU/API.
"""
from __future__ import annotations

import pytest

from reel_engine.timeline.model import storyboard as build_timeline
from script_engine import ScriptEngine

from workflow_engine.core.artifact import (
    KIND_JSON,
    KIND_STORYBOARD,
    KIND_TIMELINE,
    Artifact,
    hash_json,
)
from workflow_engine.core.codecs import get_codec
from workflow_engine.core.context import WorkflowContext
from workflow_engine.core.graph import DependencyGraph, GraphError
from workflow_engine.core.workflow import Workflow
from workflow_engine.tests.helpers import ConstStage, SumStage


# ------------------------------------------------------------------- graph
def _diamond() -> Workflow:
    return Workflow("diamond", [
        ConstStage(name="a", produces=("a",), value=1),
        SumStage(name="b", needs=("a",), produces=("b",), base=10),
        SumStage(name="c", needs=("a",), produces=("c",), base=100),
        SumStage(name="d", needs=("b", "c"), produces=("d",), base=0),
    ])


def test_topological_order_respects_dependencies():
    g = _diamond().graph
    order = g.topological_order()
    assert order[0] == "a" and order[-1] == "d"
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


def test_levels_group_independent_stages():
    g = _diamond().graph
    levels = g.levels()
    assert levels[0] == ("a",)
    assert set(levels[1]) == {"b", "c"}         # b and c are parallel-safe
    assert levels[2] == ("d",)


def test_topological_order_is_deterministic():
    g = _diamond().graph
    assert g.topological_order() == g.topological_order()


def test_unknown_dependency_is_rejected():
    with pytest.raises(GraphError, match="unknown"):
        Workflow("bad", [SumStage(name="a", needs=("ghost",), produces=("a",))])


def test_cycle_is_detected():
    with pytest.raises(GraphError, match="cycle"):
        Workflow("cyc", [
            SumStage(name="a", needs=("b",), produces=("a",)),
            SumStage(name="b", needs=("a",), produces=("b",)),
        ])


def test_duplicate_stage_name_is_rejected():
    with pytest.raises(GraphError):
        Workflow("dup", [ConstStage(name="a", produces=("a",)),
                         ConstStage(name="a", produces=("b",))])


def test_transitive_dependents():
    g = _diamond().graph
    assert set(g.transitive_dependents("a")) == {"b", "c", "d"}
    assert g.transitive_dependents("d") == ()


# --------------------------------------------------------------- signatures
def test_signature_changes_with_params():
    s1 = ConstStage(name="a", produces=("a",), value=1)
    s2 = ConstStage(name="a", produces=("a",), value=2)
    assert s1.signature() != s2.signature()
    assert s1.signature() == ConstStage(name="a", produces=("a",), value=1).signature()


# ----------------------------------------------------------- artifacts/codec
def test_artifact_identity_ignores_value():
    a = Artifact("x", KIND_JSON, "hhh", value=1)
    b = Artifact("x", KIND_JSON, "hhh", value=2)
    assert a == b                                  # identity is (name, kind, content_hash)


def test_json_codec_roundtrip(tmp_path):
    art = Artifact("m", KIND_JSON, hash_json({"k": 1}), value={"k": 1, "list": [1, 2]})
    codec = get_codec(KIND_JSON)
    ref = codec.encode(art, tmp_path)
    assert codec.decode(ref, tmp_path) == {"k": 1, "list": [1, 2]}


def test_storyboard_codec_roundtrip(tmp_path):
    sb = ScriptEngine().generate_storyboard("Test prompt about coffee", template=None)
    art = Artifact("storyboard", KIND_STORYBOARD, "h", value=sb)
    codec = get_codec(KIND_STORYBOARD)
    back = codec.decode(codec.encode(art, tmp_path), tmp_path)
    assert back.n_scenes == sb.n_scenes
    assert [s.narration for s in back.scenes] == [s.narration for s in sb.scenes]


def test_timeline_codec_roundtrip(tmp_path):
    tl = build_timeline([("blue", "Hi", 2.0), ("black", "Bye", 2.0)])
    art = Artifact("timeline", KIND_TIMELINE, "h", value=tl)
    codec = get_codec(KIND_TIMELINE)
    back = codec.decode(codec.encode(art, tmp_path), tmp_path)
    assert back.n_scenes == tl.n_scenes and back.duration_s == tl.duration_s


# ------------------------------------------------------------------ context
def test_context_lazy_decode(tmp_path):
    ctx = WorkflowContext(tmp_path)
    art = Artifact("m", KIND_JSON, hash_json({"v": 5}), value=None)
    ctx.put(art)
    codec = get_codec(KIND_JSON)
    ref = codec.encode(Artifact("m", KIND_JSON, "h", value={"v": 5}), tmp_path)
    ctx.put_ref("m", ref)
    assert ctx.value("m") == {"v": 5}              # decoded lazily from disk


def test_context_missing_artifact_raises(tmp_path):
    ctx = WorkflowContext(tmp_path)
    with pytest.raises(KeyError):
        ctx.artifact("nope")


def test_declared_artifacts_map():
    wf = _diamond()
    assert wf.declared_artifacts() == {"a": "a", "b": "b", "c": "c", "d": "d"}
