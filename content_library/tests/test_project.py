"""Project model + serde tests (Phase C15) — hermetic and deterministic."""
from __future__ import annotations

from content_library.project import (
    STATUS_DRAFT,
    STATUS_RENDERED,
    OutputRef,
    ProjectRecord,
    make_project_id,
)


def test_project_id_is_deterministic():
    a = make_project_id("My Reel", "a prompt")
    b = make_project_id("My Reel", "a prompt")
    c = make_project_id("My Reel", "different")
    assert a == b and a != c
    assert a.startswith("my-reel-")


def test_record_roundtrips_through_json():
    rec = ProjectRecord(
        project_id="p1", title="Title", prompt="prompt", template="real_estate",
        tags=("a", "b"), status=STATUS_RENDERED, presentation={"theme": "finance"},
        storyboard={"n_scenes": 5}, workflow_state={"ok": True},
        outputs=(OutputRef(kind="master", path="run/master.avi", content_hash="h",
                           width=1080, height=1920, duration_s=48.0),),
        created_at="2026-01-01T00:00:01Z", modified_at="2026-01-01T00:00:02Z")
    back = ProjectRecord.from_json(rec.to_json())
    assert back == rec
    assert back.outputs[0].width == 1080


def test_evolve_is_immutable_and_bumps_modified():
    rec = ProjectRecord(project_id="p1", title="T", created_at="t0", modified_at="t0")
    rec2 = rec.evolve(now="t1", status=STATUS_RENDERED)
    assert rec.status == STATUS_DRAFT                 # original untouched
    assert rec2.status == STATUS_RENDERED and rec2.modified_at == "t1"
    assert rec2.created_at == "t0"                    # created preserved


def test_with_tags_dedupes():
    rec = ProjectRecord(project_id="p1", title="T")
    rec2 = rec.with_tags(("x", "x", "y"), now="t1")
    assert rec2.tags == ("x", "y")


def test_summary_has_search_fields():
    rec = ProjectRecord(project_id="p1", title="T", tags=("a",), status="rendered",
                        template="real_estate", created_at="t0", modified_at="t1")
    s = rec.summary()
    assert s["project_id"] == "p1" and s["status"] == "rendered"
    assert s["tags"] == ["a"] and s["template"] == "real_estate"
