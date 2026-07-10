"""Library CRUD + search + index tests (Phase C15) — hermetic and deterministic."""
from __future__ import annotations

import pytest

from content_library import ContentLibrary, ProjectNotFound


def test_create_and_load_roundtrip(library):
    p = library.create_project("My Reel", prompt="hello", template="real_estate",
                               tags=("finance",))
    assert p.status == "draft" and p.created_at == p.modified_at
    assert library.load(p.project_id) == p


def test_duplicate_project_rejected(library):
    library.create_project("Dup", prompt="x")
    with pytest.raises(FileExistsError):
        library.create_project("Dup", prompt="x")


def test_load_missing_raises(library):
    with pytest.raises(ProjectNotFound):
        library.load("nope")


def test_delete_removes_project_and_index_entry(library):
    p = library.create_project("Temp", prompt="x")
    library.delete(p.project_id)
    assert not library.exists(p.project_id)
    assert library.search(title="Temp") == []


def test_list_projects_is_sorted(library):
    library.create_project("B proj", project_id="b")
    library.create_project("A proj", project_id="a")
    assert [p.project_id for p in library.list_projects()] == ["a", "b"]


# ---------------------------------------------------------------- search
@pytest.fixture
def populated(library):
    library.create_project("Real Estate Reel", prompt="p", template="real_estate",
                           tags=("finance", "property"), project_id="re")
    library.create_project("Coffee Ad", prompt="p", template="product",
                           tags=("food",), project_id="co")
    p = library.create_project("Property Tour", prompt="p", template="real_estate",
                               tags=("property", "luxury"), project_id="pt")
    library.save(p.evolve(now="2026-02-01T00:00:00Z", status="rendered"))
    return library


def test_search_by_title(populated):
    assert [e["project_id"] for e in populated.search(title="real")] == ["re"]


def test_search_by_tag_and_and_tags(populated):
    assert {e["project_id"] for e in populated.search(tag="property")} == {"pt", "re"}
    assert [e["project_id"] for e in populated.search(tags=("property", "luxury"))] == ["pt"]


def test_search_by_template_and_status(populated):
    assert {e["project_id"] for e in populated.search(template="real_estate")} == {"pt", "re"}
    assert [e["project_id"] for e in populated.search(status="rendered")] == ["pt"]


def test_search_by_date_range(populated):
    later = populated.search(modified_after="2026-01-15")
    assert [e["project_id"] for e in later] == ["pt"]


def test_search_sort_is_deterministic(populated):
    by_title = [e["title"] for e in populated.search(sort="title")]
    assert by_title == ["Coffee Ad", "Property Tour", "Real Estate Reel"]
    assert populated.search(sort="id") == populated.search(sort="id")


def test_index_persists_and_rebuilds(populated, tmp_path):
    # reopen the same library: index.json loads without a rebuild
    reopened = ContentLibrary(populated.root)
    assert {e["project_id"] for e in reopened.search(tag="property")} == {"pt", "re"}
    # rebuilding from manifests yields the same result
    reopened.rebuild_index()
    assert {e["project_id"] for e in reopened.search(tag="property")} == {"pt", "re"}


def test_index_missing_is_rebuilt_from_manifests(populated):
    populated.store.index_path.unlink()               # simulate a lost index
    reopened = ContentLibrary(populated.root)          # load() rebuilds it
    assert len(reopened.index) == 3
    assert populated.store.index_path.exists()
