"""Workflow Engine integration (Phase C15) — run projects through the library.

This is the bridge between the Content Library and the C14 Workflow Engine. It runs
a project's ``prompt -> export`` pipeline **rooted inside the project's own
directory**, so every workflow artifact (journal, storyboard, timeline, master,
exports) lives at ``projects/<id>/run/`` and the project is a self-contained,
portable bundle.

Crucially it **does not modify any Workflow Engine logic** — it only constructs a
``WorkflowEngine`` with the project directory as its root and reads the standard
``WorkflowResult``. Because the run directory is stable (unlike a scratch temp dir),
reloading a project and re-rendering it **reuses the cached run and reproduces
byte-identical outputs** — the guarantee the validation demo checks.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foundation.shared_utils.hashing import sha256_file

from workflow_engine import Presentation, WorkflowEngine
from workflow_engine.core.workflow import WorkflowResult

from content_library.project import (
    STATUS_RENDERED,
    OutputRef,
    ProjectRecord,
)

#: The fixed workflow run id for a project (its run dir is ``projects/<id>/run``).
RUN_ID = "run"
DEFAULT_PROFILES = ("reel_9x16", "square_1x1")


@dataclass(frozen=True)
class GenerationOutcome:
    """The result of generating/re-rendering a project."""

    record: ProjectRecord
    result: WorkflowResult


def _engine_for(library, project_id: str) -> WorkflowEngine:
    """A WorkflowEngine rooted at the project's directory (run dir = ``<dir>/run``)."""
    return WorkflowEngine(root=library.store.project_dir(project_id))


def _presentation(record: ProjectRecord) -> Presentation:
    fields = {f for f in Presentation().__dataclass_fields__}
    return Presentation(**{k: v for k, v in record.presentation.items() if k in fields})


def _relpath(path: Path | str, base: Path) -> str:
    """A POSIX path relative to the project directory (portable across machines)."""
    return Path(os.path.relpath(Path(path), base)).as_posix()


def _outputs(result: WorkflowResult, project_dir: Path) -> tuple[OutputRef, ...]:
    """Extract master + export references (paths relative to the project dir)."""
    master = result.artifact("master")
    refs = [OutputRef(kind="master", path=_relpath(master.value, project_dir),
                      content_hash=master.content_hash,
                      width=master.meta.get("width", 0), height=master.meta.get("height", 0),
                      duration_s=master.meta.get("duration_s", 0.0))]
    exports_art = result.artifact("exports")
    for e in master.meta.get("exports", []):
        refs.append(OutputRef(kind="export", profile=e.get("profile", ""),
                              path=_relpath(e["path"], project_dir),
                              content_hash=exports_art.content_hash,
                              width=e.get("width", 0), height=e.get("height", 0)))
    return tuple(refs)


def _workflow_state(result: WorkflowResult, *, renderer: str,
                    profiles: tuple[str, ...]) -> dict[str, Any]:
    """A compact, serializable snapshot of the workflow run."""
    return {
        "run_id": result.run_id,
        "renderer": renderer,
        "profiles": list(profiles),
        "ok": result.ok,
        "status_counts": result.status_counts(),
        "stages": {n: r.status.value for n, r in result.stage_results.items()},
    }


def _storyboard_summary(result: WorkflowResult, project_dir: Path) -> dict[str, Any]:
    art = result.artifact("storyboard")
    sb = art.value
    return {
        "ref": _relpath(project_dir / RUN_ID / "storyboard.json", project_dir),
        "title": getattr(sb, "title", ""),
        "n_scenes": getattr(sb, "n_scenes", art.meta.get("scenes", 0)),
        "provider": art.meta.get("provider", ""),
        "content_hash": art.content_hash,
    }


def generate_project(library, project_id: str, *, renderer: str = "mock",
                     profiles: tuple[str, ...] = DEFAULT_PROFILES,
                     force: tuple[str, ...] = (), **build_opts) -> GenerationOutcome:
    """Run a project's full pipeline and persist its outputs into the library.

    Builds a workflow from the saved project (prompt / template / presentation),
    runs it in ``projects/<id>/run``, and writes an updated, immutable record with
    the storyboard summary, workflow state, and output references."""
    record = library.load(project_id)
    project_dir = library.store.project_dir(project_id)
    engine = _engine_for(library, project_id)
    workflow = engine.build(record.prompt, template=record.template or "",
                            presentation=_presentation(record), renderer=renderer,
                            profiles=tuple(profiles), **build_opts)
    result = engine.run(workflow, run_id=RUN_ID, force=tuple(force))
    updated = record.evolve(
        now=library.now(),
        status=STATUS_RENDERED if result.ok else record.status,
        storyboard=_storyboard_summary(result, project_dir),
        workflow_state=_workflow_state(result, renderer=renderer, profiles=tuple(profiles)),
        outputs=_outputs(result, project_dir))
    library.save(updated)
    return GenerationOutcome(record=updated, result=result)


def rerender_project(library, project_id: str, *,
                     force: tuple[str, ...] = ()) -> GenerationOutcome:
    """Reload a project and re-run its workflow (resume) — reproducing its outputs.

    Rebuilds the workflow with exactly the saved settings and runs the same run id;
    unchanged inputs are reused, so the outputs are identical (byte-for-byte with
    the deterministic mock renderer)."""
    record = library.load(project_id)
    state = record.workflow_state
    renderer = state.get("renderer", "mock")
    profiles = tuple(state.get("profiles", DEFAULT_PROFILES))
    return generate_project(library, project_id, renderer=renderer,
                            profiles=profiles, force=force)


def output_hashes(library, record: ProjectRecord) -> dict[str, str]:
    """SHA-256 of each of a project's output files (for identical-output checks)."""
    project_dir = library.store.project_dir(record.project_id)
    out: dict[str, str] = {}
    for ref in record.outputs:
        path = project_dir / ref.path
        if path.exists():
            out[ref.path] = sha256_file(path)
    return out
