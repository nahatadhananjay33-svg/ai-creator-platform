"""Workflow integration tests (Phase C15) — the reload/re-render identical guarantee.

Runs the real ``prompt -> export`` pipeline through the library with the hermetic
mock voice adapter + mock (raw-AVI proxy) renderer and a low fps — no GPU, model,
ffmpeg, or network. Asserts a generated project persists its outputs, reloads
byte-identically, and re-renders (resume + forced) to the same bytes.
"""
from __future__ import annotations

import pytest

from workflow_engine import Presentation

from content_library import output_hashes

PROMPT = "Why investing in real estate early is beneficial"
PRES = Presentation(theme="finance", soundtrack="upbeat", fps=6).to_dict()


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    # module-scoped: generate once (a full mock pipeline run) and reuse.
    import itertools

    from content_library import ContentLibrary
    counter = itertools.count(1)
    lib = ContentLibrary(tmp_path_factory.mktemp("lib"),
                         clock=lambda: f"2026-01-01T00:00:{next(counter):02d}Z")
    rec = lib.create_project("Investing Reel", prompt=PROMPT, template="real_estate",
                             tags=("finance",), presentation=PRES)
    outcome = lib.generate(rec.project_id, renderer="mock")
    return lib, outcome


def test_generate_produces_outputs_and_rendered_status(generated):
    _lib, outcome = generated
    rec = outcome.record
    assert outcome.result.ok and rec.status == "rendered"
    kinds = [o.kind for o in rec.outputs]
    assert kinds.count("master") == 1 and kinds.count("export") == 2


def test_outputs_are_relative_and_exist(generated):
    lib, outcome = generated
    project_dir = lib.store.project_dir(outcome.record.project_id)
    for o in outcome.record.outputs:
        assert not o.path.startswith("/")            # portable relative path
        assert (project_dir / o.path).exists()


def test_storyboard_and_workflow_state_persisted(generated):
    _lib, outcome = generated
    rec = outcome.record
    assert rec.storyboard["n_scenes"] >= 1
    assert rec.workflow_state["ok"] and rec.workflow_state["renderer"] == "mock"


def test_reload_roundtrips(generated):
    lib, outcome = generated
    assert lib.load(outcome.record.project_id).to_dict() == outcome.record.to_dict()


def test_rerender_resume_reproduces_identical_bytes(generated):
    lib, outcome = generated
    before = output_hashes(lib, outcome.record)
    resumed = lib.rerender(outcome.record.project_id)
    assert resumed.result.status_counts()["cached"] == 10        # nothing re-ran
    assert output_hashes(lib, resumed.record) == before          # identical bytes


def test_forced_rerender_preserves_identity(generated):
    lib, outcome = generated
    before = output_hashes(lib, outcome.record)
    ch_before = {o.path: o.content_hash for o in outcome.record.outputs}
    forced = lib.generate(outcome.record.project_id, renderer="mock", force=("render",))
    assert "render" in forced.result.executed()                  # actually re-rendered
    # mock renderer is byte-deterministic -> identical bytes AND identical content hash
    assert output_hashes(lib, forced.record) == before
    assert {o.path: o.content_hash for o in forced.record.outputs} == ch_before


def test_search_finds_rendered_project(generated):
    lib, outcome = generated
    hits = lib.search(status="rendered")
    assert outcome.record.project_id in {e["project_id"] for e in hits}
