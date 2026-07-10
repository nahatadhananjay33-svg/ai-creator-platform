"""Workflow-integration tests (Phase C18) — hermetic (mock), no GPU, no APIs.

Two layers: a fast unit test over a fake result object, and one real end-to-end run
(Workflow Engine -> Quality PASS -> Upload Assistant -> files) that IS the phase's
validation — generate one reel, generate metadata, verify the outputs and files.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from upload_engine import (
    generate_from_result,
    generate_upload_assets,
    summary_from_result,
)
from upload_engine.tests.conftest import StubStoryboard


# ---- fast unit test: read a (fake) workflow result --------------------------

@dataclass
class FakeArtifact:
    value: Any = None
    meta: dict = field(default_factory=dict)


@dataclass
class FakeResult:
    artifacts: dict

    def artifact(self, name):
        return self.artifacts[name]


def _fake_result():
    tl = SimpleNamespace(duration_s=42.0, meta=SimpleNamespace(aspect="9:16"))
    return FakeResult({
        "storyboard": FakeArtifact(value=StubStoryboard()),
        "timeline": FakeArtifact(value=tl),
        "master": FakeArtifact(meta={"duration_s": 42.0,
                                     "exports": [{"aspect": "9:16"}]}),
    })


def test_summary_from_result_reads_storyboard_and_timeline():
    summary = summary_from_result(_fake_result())
    assert summary.title.startswith("Why investing")
    assert summary.duration_s == 42.0 and summary.aspect == "9:16"


def test_duration_falls_back_to_master_when_no_timeline():
    result = _fake_result()
    result.artifacts["timeline"] = FakeArtifact(value=None)
    summary = summary_from_result(result)
    assert summary.duration_s == 42.0 and summary.aspect == "9:16"


def test_generate_from_result_is_complete():
    md = generate_from_result(_fake_result())
    assert md.is_complete
    assert md.template == "real_estate"


def test_generate_upload_assets_writes_files(tmp_path):
    md, files = generate_upload_assets(_fake_result(), tmp_path)
    assert files.metadata_json.exists() and files.preview_md.exists()
    assert md.is_complete


# ---- end-to-end validation: one real reel through the whole flow ------------

@pytest.fixture(scope="module")
def workflow_result(tmp_path_factory):
    """Generate one reel with the hermetic mock renderer."""
    from workflow_engine import WorkflowEngine

    root = tmp_path_factory.mktemp("upload_e2e")
    engine = WorkflowEngine(root=root)
    workflow = engine.build("Why investing in real estate early is beneficial",
                            template="real_estate", renderer="mock",
                            profiles=("reel_9x16", "square_1x1"))
    return engine.run(workflow, run_id="reel")


def test_reel_generated_and_passes_quality(workflow_result):
    from quality_engine import check_workflow_result

    assert workflow_result.ok
    assert check_workflow_result(workflow_result).ok


def test_metadata_generated_for_real_reel(workflow_result, tmp_path):
    # Generate metadata (Validation: required fields present, no empty outputs).
    metadata, files = generate_upload_assets(workflow_result, tmp_path / "upload",
                                             template="real_estate")
    assert metadata.missing_fields() == ()
    assert metadata.is_complete
    assert metadata.youtube_title
    assert metadata.hashtags
    # Files generated.
    assert files.metadata_json.exists() and files.preview_md.exists()
    assert files.metadata_json.stat().st_size > 0
    assert files.preview_md.stat().st_size > 0
    # Real render facts flowed through.
    assert metadata.duration_s > 0
    assert metadata.aspect == "9:16"


def test_metadata_default_template_follows_storyboard(workflow_result, tmp_path):
    # No explicit template -> uses the storyboard's own vertical.
    md = generate_from_result(workflow_result)
    assert md.template == "real_estate"
