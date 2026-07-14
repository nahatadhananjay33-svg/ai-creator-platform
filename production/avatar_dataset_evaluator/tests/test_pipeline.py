"""End-to-end pipeline on synthetic videos (mechanics; hermetic, CPU, offline)."""
from __future__ import annotations

from production.avatar_dataset_evaluator.config import Config, Paths
from production.avatar_dataset_evaluator.pipeline import evaluate_dataset
from production.avatar_dataset_evaluator.probe import probe
from production.avatar_dataset_evaluator.storage import write_sqlite


def test_probe_reads_synthetic(tmp_path, make_video):
    v = make_video(tmp_path / "clip.mp4", w=320, h=240, frames=20, fps=10)
    m = probe(v)
    assert m.width == 320 and m.height == 240
    assert m.frame_count >= 15 and m.duration > 0
    assert m.orientation == "landscape"


def test_pipeline_and_resume(tmp_path, make_video):
    root = tmp_path / "data"
    src = root / "raw_videos" / "folderA"
    src.mkdir(parents=True)
    make_video(src / "clip1.mp4")
    make_video(src / "clip2.mp4")
    paths = Paths.make(root).ensure()

    recs = evaluate_dataset(paths, Config(), progress=False)
    assert len(recs) == 2
    # synthetic frames have no real face -> rejected; still routed + thumbnailed
    assert all(not r.accepted for r in recs)
    assert (paths.rejected).exists()
    assert list(paths.thumbnails.glob("*.jpg"))

    write_sqlite(recs, paths.out / "dataset.sqlite")
    recs2 = evaluate_dataset(paths, Config(), progress=False)   # resume
    assert len(recs2) == 2          # both already processed -> loaded, none re-run


def test_reports_produced(tmp_path, make_video):
    root = tmp_path / "data"
    src = root / "raw_videos"
    src.mkdir(parents=True)
    make_video(src / "clip1.mp4")
    from production.avatar_dataset_evaluator.evaluate import main
    rc = main(["--base", str(root), "--sample-n", "5"])
    assert rc == 0
    out = root / "avatar_dataset"
    for f in ("dataset.sqlite", "dataset.csv", "dataset.xlsx"):
        assert (out / f).exists(), f
    assert (out / "reports" / "report.json").exists()
    assert (out / "reports" / "report.txt").exists()
