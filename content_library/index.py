"""The library index + deterministic search (Phase C15).

A single ``index.json`` holds a compact summary of every project so search never
has to open each manifest. Search is **purely deterministic and rule-based** — no
vector database, no embeddings — filtering the summaries by title (case-insensitive
substring), tag (membership), date range (lexicographic on ISO timestamps),
type/template, and status, then applying a stable sort. The same query over the
same library always returns the same ordered result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_library.store import LibraryStore, read_json, write_json

INDEX_SCHEMA_VERSION = 1

#: Supported sort orders (all total orders — ties broken by project_id).
SORTS = ("modified_desc", "modified_asc", "created_desc", "created_asc", "title", "id")


@dataclass(frozen=True)
class SearchQuery:
    """A deterministic project query (empty fields are ignored)."""

    title: str = ""                     # case-insensitive substring of the title
    tag: str = ""                       # a single tag that must be present
    tags: tuple[str, ...] = ()          # every tag must be present (AND)
    status: str = ""                    # exact status
    template: str = ""                  # exact template ("type")
    created_after: str = ""             # ISO, inclusive
    created_before: str = ""            # ISO, inclusive
    modified_after: str = ""            # ISO, inclusive
    modified_before: str = ""           # ISO, inclusive
    sort: str = "modified_desc"

    def matches(self, e: dict[str, Any]) -> bool:
        if self.title and self.title.lower() not in e.get("title", "").lower():
            return False
        tags = set(e.get("tags", ()))
        if self.tag and self.tag not in tags:
            return False
        if self.tags and not set(self.tags).issubset(tags):
            return False
        if self.status and e.get("status", "") != self.status:
            return False
        if self.template and e.get("template", "") != self.template:
            return False
        created, modified = e.get("created_at", ""), e.get("modified_at", "")
        if self.created_after and created < self.created_after:
            return False
        if self.created_before and created > self.created_before:
            return False
        if self.modified_after and modified < self.modified_after:
            return False
        if self.modified_before and modified > self.modified_before:
            return False
        return True


def _sort_key(sort: str):
    """A (key_fn, reverse) pair for a stable sort; ties always break by id."""
    pid = lambda e: e.get("project_id", "")
    table = {
        "modified_desc": (lambda e: (e.get("modified_at", ""), pid(e)), True),
        "modified_asc": (lambda e: (e.get("modified_at", ""), pid(e)), False),
        "created_desc": (lambda e: (e.get("created_at", ""), pid(e)), True),
        "created_asc": (lambda e: (e.get("created_at", ""), pid(e)), False),
        "title": (lambda e: (e.get("title", "").lower(), pid(e)), False),
        "id": (pid, False),
    }
    return table.get(sort, table["modified_desc"])


class LibraryIndex:
    """Maintains ``index.json`` and answers deterministic search queries."""

    def __init__(self, store: LibraryStore) -> None:
        self.store = store
        self._entries: dict[str, dict[str, Any]] = {}

    # ---- persistence ---------------------------------------------------------
    def load(self) -> "LibraryIndex":
        """Load the index, rebuilding it from manifests if it is missing/stale."""
        if self.store.index_path.exists():
            data = read_json(self.store.index_path)
            self._entries = {e["project_id"]: e for e in data.get("projects", [])}
        else:
            self.rebuild()
        return self

    def save(self) -> None:
        entries = [self._entries[k] for k in sorted(self._entries)]
        write_json(self.store.index_path,
                   {"schema_version": INDEX_SCHEMA_VERSION, "projects": entries})

    def rebuild(self) -> "LibraryIndex":
        """Rebuild the index by scanning every project manifest on disk."""
        from content_library.project import ProjectRecord
        self._entries = {}
        for pid in self.store.list_project_ids():
            record = ProjectRecord.from_dict(read_json(self.store.manifest_path(pid)))
            self._entries[pid] = record.summary()
        self.save()
        return self

    # ---- mutation ------------------------------------------------------------
    def upsert(self, summary: dict[str, Any]) -> None:
        self._entries[summary["project_id"]] = dict(summary)
        self.save()

    def remove(self, project_id: str) -> None:
        self._entries.pop(project_id, None)
        self.save()

    # ---- query ---------------------------------------------------------------
    def entries(self) -> list[dict[str, Any]]:
        return [self._entries[k] for k in sorted(self._entries)]

    def search(self, query: SearchQuery) -> list[dict[str, Any]]:
        matched = [e for e in self._entries.values() if query.matches(e)]
        key_fn, reverse = _sort_key(query.sort)
        return sorted(matched, key=key_fn, reverse=reverse)

    def __len__(self) -> int:
        return len(self._entries)
