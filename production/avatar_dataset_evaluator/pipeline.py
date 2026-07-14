"""Orchestrate per-video evaluation: probe -> analyze -> classify -> route."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List

from .analyze import analyze
from .classify import evaluate as classify_eval
from .config import Config, Paths, VIDEO_EXTS
from .models import Record, VideoMeta, VisualAnalysis
from .probe import probe
from .storage import load_records
from .thumbnails import make_thumbnail


def _list_videos(source: Path) -> List[Path]:
    return sorted((p for p in Path(source).rglob("*") if p.suffix.lower() in VIDEO_EXTS),
                  key=lambda x: x.as_posix())


def _route(src: Path, dst_dir: Path) -> str:
    dst = Path(dst_dir) / src.name
    if dst.exists():
        return str(dst)
    try:
        os.link(src, dst)                    # hardlink (same volume -> no extra space)
    except OSError:
        try:
            shutil.copyfile(src, dst)
        except OSError:
            return ""
    return str(dst)


def _progress(it, total, on):
    if not on:
        return it
    try:
        from tqdm.auto import tqdm
        return tqdm(it, total=total, desc="videos", unit="vid")
    except Exception:
        return it


def _record(idx: int, src: Path, m: VideoMeta, a: VisualAnalysis,
            quality, accepted: bool, accept_reason: str, reject_reason: str,
            score: float, thumb: str, routed: str, source_rel: str) -> Record:
    return Record(
        id=idx, filename=m.filename, source=source_rel,
        duration=m.duration, resolution=f"{m.width}x{m.height}", width=m.width, height=m.height,
        fps=m.fps, aspect_ratio=m.aspect_ratio, orientation=m.orientation,
        file_size_mb=m.file_size_mb, codec=m.codec, bitrate=m.bitrate,
        frame_count=m.frame_count, creation_time=m.creation_time,
        face_visibility_pct=a.face_visibility_pct, avg_face_size_pct=a.avg_face_size_pct,
        frontal_pct=a.frontal_pct, profile_pct=a.profile_pct, face_view=a.face_view,
        head_rotation=a.head_rotation, lighting_mean=a.lighting_mean,
        lighting_consistency=a.lighting_consistency, camera_stability=a.camera_stability,
        motion_blur=a.motion_blur, occlusion_pct=a.occlusion_pct,
        eye_visibility_pct=a.eye_visibility_pct, mouth_visibility_pct=a.mouth_visibility_pct,
        speaking_pct=a.speaking_pct, walking_pct=a.walking_pct, stationary_pct=a.stationary_pct,
        camera_movement=a.camera_movement, scene_changes=a.scene_changes,
        time_of_day=a.time_of_day, setting=a.setting, expression=a.expression,
        quality=quality.value, accepted=accepted, accept_reason=accept_reason,
        reject_reason=reject_reason, avatar_score=score, thumbnail_path=thumb)


def evaluate_dataset(paths: Paths, cfg: Config, resume: bool = True,
                     progress: bool = True) -> List[Record]:
    paths.ensure()
    prior = load_records(paths.out / "dataset.sqlite") if resume else []
    done = {r.filename for r in prior}
    videos = [v for v in _list_videos(paths.source) if v.name not in done]

    records: List[Record] = list(prior)
    from .models import Quality
    for v in _progress(videos, len(videos), progress):
        rel = v.relative_to(paths.source).as_posix()
        try:
            m = probe(v)
            a = analyze(v, m, cfg)
            quality, accepted, ar, rr, score = classify_eval(m, a, cfg)
            thumb = make_thumbnail(v, paths.thumbnails, m)
            routed = _route(v, paths.accepted if accepted else paths.rejected)
            records.append(_record(0, v, m, a, quality, accepted, ar, rr, score, thumb, routed, rel))
        except Exception as e:                # never let one bad file stop the run
            from .analyze import _empty
            m = VideoMeta(v.name, 0.0, 0, 0, 0.0, 0.0, "landscape", 0.0, "", 0, 0)
            records.append(_record(0, v, m, _empty(m), Quality.REJECT, False, "",
                                   f"analysis failed: {e}", 0.0, "", "", rel))

    for i, r in enumerate(records, 1):
        r.id = i
    return records
