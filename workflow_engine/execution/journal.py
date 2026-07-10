"""The run journal (Phase C14) — persisted state for resume and the incremental cache.

Every run owns a directory holding one ``journal.json``. After each stage the
executor records, per stage: its ``input_hash`` (the incremental cache key), its
status, and a payload ref for each produced artifact (enough for a codec to reload
the value in a fresh process). On the next run the executor loads the journal and,
for each stage whose recomputed ``input_hash`` matches the recorded one *and*
whose artifact payloads still exist, reuses the recorded outputs instead of
re-executing — that single mechanism delivers both **resume** (continue an
interrupted run) and **incremental execution** (unchanged inputs -> reuse).

The journal is deliberately plain JSON with stable key order so it is diff-friendly
and never embeds a timestamp that would defeat determinism.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from workflow_engine.core.artifact import Artifact
from workflow_engine.core.codecs import get_codec

JOURNAL_NAME = "journal.json"
JOURNAL_SCHEMA_VERSION = 1


@dataclass
class StageRecord:
    """One stage's persisted outcome (the resume/cache unit)."""

    name: str
    status: str
    input_hash: str
    #: artifact name -> {"descriptor": {...}, "ref": {...codec payload ref...}}
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    error: str | None = None

    def artifact_names(self) -> tuple[str, ...]:
        return tuple(self.outputs.keys())


class RunJournal:
    """Reads/writes the per-run ``journal.json`` and reconstructs cached artifacts."""

    def __init__(self, run_dir: Path | str) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.records: dict[str, StageRecord] = {}
        self.run_id: str = ""
        self.workflow: str = ""

    @property
    def path(self) -> Path:
        return self.run_dir / JOURNAL_NAME

    # ---- load ----------------------------------------------------------------
    @classmethod
    def load(cls, run_dir: Path | str) -> "RunJournal":
        journal = cls(run_dir)
        if journal.path.exists():
            data = json.loads(journal.path.read_text(encoding="utf-8"))
            journal.run_id = data.get("run_id", "")
            journal.workflow = data.get("workflow", "")
            for name, rec in data.get("stages", {}).items():
                journal.records[name] = StageRecord(
                    name=name,
                    status=rec.get("status", "pending"),
                    input_hash=rec.get("input_hash", ""),
                    outputs=rec.get("outputs", {}),
                    error=rec.get("error"),
                )
        return journal

    # ---- queries -------------------------------------------------------------
    def record(self, name: str) -> StageRecord | None:
        return self.records.get(name)

    def outputs_present(self, name: str) -> bool:
        """True if every persisted artifact payload for ``name`` still exists on disk."""
        rec = self.records.get(name)
        if rec is None:
            return False
        for out in rec.outputs.values():
            ref = out.get("ref", {})
            payload = ref.get("payload")
            if payload is not None and not (self.run_dir / payload).exists():
                return False
            path = ref.get("path")
            if path is not None and not Path(path).exists():
                return False
            for p in ref.get("paths", []):
                if not Path(p).exists():
                    return False
        return True

    def reusable(self, name: str, input_hash: str) -> bool:
        """A stage is reusable iff it completed before with the same input hash and
        all of its artifact payloads are still on disk."""
        rec = self.records.get(name)
        return (rec is not None and rec.status in ("completed", "cached", "skipped")
                and rec.input_hash == input_hash and self.outputs_present(name))

    def load_artifacts(self, name: str) -> dict[str, Artifact]:
        """Rebuild the cached artifacts for ``name`` (values decoded lazily later)."""
        rec = self.records[name]
        out: dict[str, Artifact] = {}
        for art_name, entry in rec.outputs.items():
            d = entry["descriptor"]
            out[art_name] = Artifact(
                name=d["name"], kind=d["kind"], content_hash=d["content_hash"],
                value=None,
                path=Path(d["path"]) if d.get("path") else None,
                meta=d.get("meta", {}), producer=d.get("producer", ""))
        return out

    def load_refs(self, name: str) -> dict[str, dict[str, Any]]:
        """The codec payload refs for ``name`` so the context can decode on demand."""
        rec = self.records[name]
        return {art_name: entry["ref"] for art_name, entry in rec.outputs.items()}

    # ---- writes --------------------------------------------------------------
    def upsert(self, name: str, status: str, input_hash: str,
               artifacts: dict[str, Artifact], error: str | None = None) -> None:
        """Persist a stage's outcome, encoding each artifact via its codec."""
        outputs: dict[str, dict[str, Any]] = {}
        for art_name, art in artifacts.items():
            ref = get_codec(art.kind).encode(art, self.run_dir)
            outputs[art_name] = {"descriptor": art.descriptor(), "ref": ref}
        self.records[name] = StageRecord(name=name, status=status,
                                         input_hash=input_hash, outputs=outputs,
                                         error=error)

    def mark(self, name: str, status: str, input_hash: str = "",
             error: str | None = None) -> None:
        """Record a stage outcome that produced no (new) artifacts (e.g. a failure)."""
        rec = self.records.get(name)
        outputs = rec.outputs if rec is not None else {}
        ih = input_hash or (rec.input_hash if rec else "")
        self.records[name] = StageRecord(name=name, status=status,
                                         input_hash=ih, outputs=outputs, error=error)

    def save(self, run_id: str, workflow: str) -> Path:
        self.run_id = run_id
        self.workflow = workflow
        data = {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "run_id": run_id,
            "workflow": workflow,
            "stages": {
                name: {
                    "status": rec.status,
                    "input_hash": rec.input_hash,
                    "outputs": rec.outputs,
                    "error": rec.error,
                }
                for name, rec in self.records.items()
            },
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        return self.path
