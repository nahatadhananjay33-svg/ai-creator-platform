"""AI Creator Platform — Version 1.0 usability layer (Phase C19).

``creator`` is the single-user front door to the platform. It owns no
generation logic of its own: it composes the engines that already exist —
Workflow Engine (prompt -> reel), Quality Engine (PASS/FAIL gate), and the
Upload Assistant (upload-ready metadata) — behind one command:

    python -m creator.run

and one standardized place for everything you produce (see :mod:`creator.paths`)
and one documented configuration file (see :mod:`creator.config`).

Everything is single-user and local: no cloud, no SaaS, no publishing. The
command writes files you copy into each platform yourself.
"""
from __future__ import annotations

from creator.config import CreatorConfig, load_creator_config
from creator.errors import CreatorError
from creator.paths import Workspace, resolve_workspace

#: Semantic version of the platform release this package finalizes.
VERSION = "1.0.0"

__all__ = [
    "VERSION",
    "CreatorConfig",
    "load_creator_config",
    "CreatorError",
    "Workspace",
    "resolve_workspace",
]
