"""The Content Library facade (Phase C15) — single-user, local, no cloud/DB/auth.

:class:`ContentLibrary` is the entry point: open (or create) a library at a root
directory and manage projects as immutable :class:`ProjectRecord` manifests on
disk. Times come from an injectable ``clock`` so the whole library is deterministic
under test. Search (M2), content pools (M3), and Workflow Engine integration (M4)
layer on top of this facade without changing it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from foundation.constants.paths import PROJECT_ROOT
from foundation.logging import get_logger
from foundation.shared_utils.timing import utc_now_iso

from content_library.index import LibraryIndex, SearchQuery
from content_library.project import ProjectRecord, make_project_id
from content_library.store import LibraryStore, read_json, write_json

logger = get_logger("content_library")

#: The default on-disk location of the library (a sibling of the engines).
DEFAULT_ROOT = PROJECT_ROOT / "content_library" / "data"


class ProjectNotFound(KeyError):
    """No project with the given id exists in the library."""


class ContentLibrary:
    """Open or create a local content library and manage its projects."""

    def __init__(self, root: Path | str | None = None,
                 *, clock: Callable[[], str] = utc_now_iso) -> None:
        self.store = LibraryStore(root if root is not None else DEFAULT_ROOT)
        self.store.ensure_layout()
        self._clock = clock
        self.index = LibraryIndex(self.store).load()

    @classmethod
    def open(cls, root: Path | str, **kwargs) -> "ContentLibrary":
        return cls(root, **kwargs)

    @property
    def root(self) -> Path:
        return self.store.root

    # ---- create / save / load ------------------------------------------------
    def create_project(
        self,
        title: str,
        *,
        prompt: str = "",
        template: str = "",
        tags: tuple[str, ...] = (),
        presentation: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> ProjectRecord:
        """Create and persist a new draft project (deterministic id from title+prompt)."""
        pid = project_id or make_project_id(title, prompt)
        if self.store.project_exists(pid):
            raise FileExistsError(f"project {pid!r} already exists")
        now = self._clock()
        record = ProjectRecord(
            project_id=pid, title=title, prompt=prompt, template=template,
            tags=tuple(dict.fromkeys(tags)), presentation=dict(presentation or {}),
            created_at=now, modified_at=now)
        self.save(record)
        logger.info("Project created", extra={"context": {"project_id": pid,
                                                          "title": title}})
        return record

    def save(self, record: ProjectRecord) -> ProjectRecord:
        """Write a project's manifest (overwriting any prior snapshot)."""
        write_json(self.store.manifest_path(record.project_id), record.to_dict())
        self._on_change(record)
        return record

    def load(self, project_id: str) -> ProjectRecord:
        """Read a project manifest back into an immutable record."""
        path = self.store.manifest_path(project_id)
        if not path.exists():
            raise ProjectNotFound(project_id)
        return ProjectRecord.from_dict(read_json(path))

    def exists(self, project_id: str) -> bool:
        return self.store.project_exists(project_id)

    def delete(self, project_id: str, *, remove_files: bool = True) -> None:
        """Delete a project (its whole directory unless ``remove_files`` is False)."""
        if not self.store.project_exists(project_id):
            raise ProjectNotFound(project_id)
        if remove_files:
            import shutil
            shutil.rmtree(self.store.project_dir(project_id), ignore_errors=True)
        else:
            self.store.manifest_path(project_id).unlink(missing_ok=True)
        self._on_delete(project_id)
        logger.info("Project deleted", extra={"context": {"project_id": project_id}})

    # ---- listing -------------------------------------------------------------
    def project_ids(self) -> list[str]:
        return self.store.list_project_ids()

    def list_projects(self) -> list[ProjectRecord]:
        """Every project, ordered by id (deterministic)."""
        return [self.load(pid) for pid in self.project_ids()]

    # ---- search --------------------------------------------------------------
    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Deterministic search returning project summaries (see :class:`SearchQuery`).

        Filter by ``title`` (substring), ``tag`` / ``tags`` (membership), ``status``,
        ``template`` (type), and ``created_*`` / ``modified_*`` ISO date ranges; order
        with ``sort``. No vector database, no embeddings."""
        return self.index.search(SearchQuery(**kwargs))

    def find(self, query: SearchQuery) -> list[ProjectRecord]:
        """Like :meth:`search` but returns full loaded records for a query object."""
        return [self.load(e["project_id"]) for e in self.index.search(query)]

    def rebuild_index(self) -> None:
        """Rebuild ``index.json`` by scanning every manifest (self-healing)."""
        self.index.rebuild()

    # ---- index maintenance hooks --------------------------------------------
    def _on_change(self, record: ProjectRecord) -> None:
        self.index.upsert(record.summary())

    def _on_delete(self, project_id: str) -> None:
        self.index.remove(project_id)

    # ---- time ----------------------------------------------------------------
    def now(self) -> str:
        return self._clock()
