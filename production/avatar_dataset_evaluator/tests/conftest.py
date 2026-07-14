"""Hermetic fixtures: OpenCV-written synthetic videos, a Record factory, no network."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from production.avatar_dataset_evaluator.models import Record, RECORD_COLUMNS


def _make_video(path: Path, w=320, h=240, frames=30, fps=15) -> Path:
    import cv2
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    for i in range(frames):
        f = np.full((h, w, 3), 70, np.uint8)
        cv2.rectangle(f, (40 + i, 60), (120 + i, 160), (200, 200, 200), -1)
        vw.write(f)
    vw.release()
    return path


@pytest.fixture
def make_video():
    return _make_video


_REC_DEFAULTS = dict(
    id=0, filename="v.mp4", source="v.mp4", duration=10.0, resolution="1080x1920",
    width=1080, height=1920, fps=30.0, aspect_ratio=0.56, orientation="portrait",
    file_size_mb=20.0, codec="h264", bitrate=5_000_000, frame_count=300, creation_time="",
    face_visibility_pct=90.0, avg_face_size_pct=5.0, frontal_pct=90.0, profile_pct=10.0,
    face_view="frontal", head_rotation="near_frontal", lighting_mean=120.0,
    lighting_consistency=0.9, camera_stability=0.95, motion_blur=300.0, occlusion_pct=5.0,
    eye_visibility_pct=80.0, mouth_visibility_pct=60.0, speaking_pct=40.0, walking_pct=0.0,
    stationary_pct=100.0, camera_movement=0.05, scene_changes=0, time_of_day="morning",
    setting="indoor?", expression="talking", quality="good", accepted=True,
    accept_reason="ok", reject_reason="", avatar_score=75.0, thumbnail_path="")


@pytest.fixture
def rec():
    def _rec(**over):
        d = dict(_REC_DEFAULTS)
        d.update(over)
        return Record(**{c: d[c] for c in RECORD_COLUMNS})
    return _rec


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    import socket

    def _blocked(*a, **k):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
