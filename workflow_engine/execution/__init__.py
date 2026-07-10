"""Workflow execution (Phase C14) — the deterministic executor and run journal.

The :class:`WorkflowExecutor` runs (or resumes) a workflow with retry and
incremental reuse; the :class:`RunJournal` persists each stage's input hash and
artifact payloads so a run can continue in a fresh process and unchanged stages
can be skipped.
"""
from __future__ import annotations

from workflow_engine.execution.executor import DEFAULT_ROOT, WorkflowExecutor
from workflow_engine.execution.journal import RunJournal, StageRecord

__all__ = ["WorkflowExecutor", "DEFAULT_ROOT", "RunJournal", "StageRecord"]
