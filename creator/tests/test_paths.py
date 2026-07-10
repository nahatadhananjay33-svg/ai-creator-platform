"""Standardized workspace layout."""
from __future__ import annotations

import pytest

from creator.paths import (
    DEFAULT_WORKSPACE,
    WORKSPACE_DIRS,
    Workspace,
    resolve_workspace,
)


def test_standardized_folder_set():
    assert WORKSPACE_DIRS == (
        "projects", "exports", "cache", "assets",
        "voices", "avatars", "music", "logs",
    )


def test_resolve_default_root():
    ws = resolve_workspace(None)
    assert ws.root == DEFAULT_WORKSPACE


def test_empty_string_root_falls_back_to_default():
    assert resolve_workspace("").root == DEFAULT_WORKSPACE


def test_resolve_custom_root(tmp_path):
    ws = resolve_workspace(tmp_path / "ws")
    assert ws.root == tmp_path / "ws"


def test_ensure_creates_every_folder(tmp_path):
    ws = resolve_workspace(tmp_path / "ws").ensure()
    assert ws.root.is_dir()
    for name in WORKSPACE_DIRS:
        assert (ws.root / name).is_dir(), name


def test_named_properties_match_folders(tmp_path):
    ws = Workspace(root=tmp_path / "ws")
    assert ws.projects == ws.root / "projects"
    assert ws.exports == ws.root / "exports"
    assert ws.logs == ws.root / "logs"


def test_path_rejects_unknown_folder(tmp_path):
    ws = Workspace(root=tmp_path / "ws")
    with pytest.raises(KeyError):
        ws.path("nope")
