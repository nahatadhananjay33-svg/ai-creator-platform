"""The library storage layer (Phase C15) — local folders + JSON, nothing else.

Single-user, local-only: no database server, no cloud, no auth. The store owns the
on-disk layout and the (deterministic) JSON read/write primitives every other
module builds on. Everything lives under one library root so backup is a folder
copy and the whole library is portable between VS Code and Colab.

    content_library/
      index.json          library-wide project index (fast search)
      projects/<id>/       one directory per project
        project.json       the immutable ProjectRecord manifest
        run/               the Workflow Engine run directory for this project
      assets/  voices/  avatars/  music/  brands/  exports/   content pools
      cache/               library-level scratch
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: Every top-level content folder the library manages.
POOL_DIRS: tuple[str, ...] = (
    "projects", "assets", "voices", "avatars", "music", "brands", "exports", "cache")

INDEX_NAME = "index.json"
MANIFEST_NAME = "project.json"
RUN_DIRNAME = "run"


def write_json(path: Path, obj: Any) -> Path:
    """Write ``obj`` as pretty, stable JSON (created parents), returning the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class LibraryStore:
    """Owns the library's directory layout and JSON I/O."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def ensure_layout(self) -> "LibraryStore":
        """Create the library root and every pool directory (idempotent)."""
        self.root.mkdir(parents=True, exist_ok=True)
        for name in POOL_DIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        return self

    # ---- top-level paths -----------------------------------------------------
    @property
    def index_path(self) -> Path:
        return self.root / INDEX_NAME

    def pool_dir(self, name: str) -> Path:
        if name not in POOL_DIRS:
            raise KeyError(f"unknown pool {name!r} (known: {list(POOL_DIRS)})")
        return self.root / name

    # ---- project paths -------------------------------------------------------
    @property
    def projects_dir(self) -> Path:
        return self.root / "projects"

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def manifest_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / MANIFEST_NAME

    def run_dir(self, project_id: str) -> Path:
        return self.project_dir(project_id) / RUN_DIRNAME

    def project_exists(self, project_id: str) -> bool:
        return self.manifest_path(project_id).exists()

    def list_project_ids(self) -> list[str]:
        """Every project id on disk, sorted (a project is a dir with a manifest)."""
        if not self.projects_dir.exists():
            return []
        ids = [p.name for p in self.projects_dir.iterdir()
               if p.is_dir() and (p / MANIFEST_NAME).exists()]
        return sorted(ids)
