"""The workflow context (Phase C14) — the artifact store passed to every stage.

A :class:`WorkflowContext` carries the produced artifacts (by name), the run
working directory (where stages write files and codecs persist payloads), and a
small immutable ``params`` mapping for run-wide values. Stages *read* their inputs
through :meth:`value` / :meth:`require` and *return* new artifacts; a stage never
mutates the context directly — the executor is the only writer. That keeps stages
in the same dependency level independent and parallel-safe.

``value(name)`` returns an artifact's live Python object, decoding it lazily from
disk (via its codec) when the value is absent — which is what makes a resumed run
in a fresh process transparent to downstream stages.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from workflow_engine.core.artifact import Artifact
from workflow_engine.core.codecs import get_codec


class WorkflowContext:
    """Mutable-by-the-executor store of artifacts for one run."""

    def __init__(self, work_dir: Path | str, params: dict[str, Any] | None = None) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.params: dict[str, Any] = dict(params or {})
        self._artifacts: dict[str, Artifact] = {}
        #: payload refs from a resumed journal, for lazy decode of cold artifacts
        self._refs: dict[str, dict[str, Any]] = {}

    # ---- writes (executor only) ---------------------------------------------
    def put(self, artifact: Artifact) -> None:
        self._artifacts[artifact.name] = artifact

    def put_ref(self, name: str, ref: dict[str, Any]) -> None:
        """Record a payload ref (from the journal) so ``value`` can decode lazily."""
        self._refs[name] = ref

    # ---- reads (stages) ------------------------------------------------------
    def has(self, name: str) -> bool:
        return name in self._artifacts

    def artifact(self, name: str) -> Artifact:
        try:
            return self._artifacts[name]
        except KeyError:
            raise KeyError(f"artifact {name!r} not available "
                           f"(present: {sorted(self._artifacts)})") from None

    def value(self, name: str) -> Any:
        """The live Python object for ``name`` (decoded from disk on a cold resume)."""
        art = self.artifact(name)
        if art.value is not None:
            return art.value
        ref = self._refs.get(name)
        if ref is not None:
            decoded = get_codec(art.kind).decode(ref, self.work_dir)
            # cache the decoded value so repeated reads are cheap
            self._artifacts[name] = art.with_value(decoded)
            return decoded
        return None

    def require(self, name: str) -> Any:
        """Like :meth:`value` but raises if the artifact/value is missing."""
        val = self.value(name)
        if val is None and self.artifact(name).kind not in ("file", "fileset"):
            raise KeyError(f"required artifact {name!r} has no value")
        return val

    def artifacts(self) -> dict[str, Artifact]:
        return dict(self._artifacts)

    # ---- files ---------------------------------------------------------------
    def stage_dir(self, name: str) -> Path:
        """A per-stage subdirectory for that stage's file outputs."""
        d = self.work_dir / name
        d.mkdir(parents=True, exist_ok=True)
        return d
