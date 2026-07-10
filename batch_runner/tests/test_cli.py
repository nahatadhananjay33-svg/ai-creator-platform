"""The batch CLI: happy path (injected runner), errors, and report output."""
from __future__ import annotations

import json

from batch_runner.report import REPORT_JSON, SUMMARY_MD
from batch_runner.run import main


def _write_csv(tmp_path):
    p = tmp_path / "reels.csv"
    p.write_text(
        "prompt,template,output\n"
        "Save money fast,finance,reel_one\n"
        "Buy your first home,real_estate,reel_two\n",
        encoding="utf-8",
    )
    return p


def test_cli_happy_path_writes_reports(tmp_path, capsys):
    csv = _write_csv(tmp_path)
    ws = tmp_path / "ws"
    code = main(["--workspace", str(ws), "--quiet", str(csv)],
                reel_runner=lambda cfg, name: 0)
    assert code == 0

    batch_dir = ws / "batch"
    report = json.loads((batch_dir / REPORT_JSON).read_text(encoding="utf-8"))
    assert report["passed"] == 2 and report["failed"] == 0
    assert (batch_dir / SUMMARY_MD).exists()
    out = capsys.readouterr().out
    assert "BATCH COMPLETE" in out


def test_cli_returns_2_when_a_reel_fails(tmp_path):
    csv = _write_csv(tmp_path)
    ws = tmp_path / "ws"
    code = main(["--workspace", str(ws), "--quiet", str(csv)],
                reel_runner=lambda cfg, name: 2 if name == "reel-two" else 0)
    assert code == 2
    report = json.loads((ws / "batch" / REPORT_JSON).read_text(encoding="utf-8"))
    assert report["passed"] == 1 and report["failed"] == 1


def test_cli_bad_input_is_reported_cleanly(tmp_path, capsys):
    code = main([str(tmp_path / "missing.csv")])
    assert code == 1
    err = capsys.readouterr().err
    assert "Error:" in err and "Hint:" in err


def test_cli_resume_second_run_skips(tmp_path):
    csv = _write_csv(tmp_path)
    ws = tmp_path / "ws"
    main(["--workspace", str(ws), "--quiet", str(csv)], reel_runner=lambda c, n: 0)

    called = []

    def runner(cfg, name):
        called.append(name)
        return 0

    code = main(["--workspace", str(ws), "--quiet", str(csv)], reel_runner=runner)
    assert code == 0
    assert called == []                                   # all skipped on resume
    report = json.loads((ws / "batch" / REPORT_JSON).read_text(encoding="utf-8"))
    assert report["skipped"] == 2
