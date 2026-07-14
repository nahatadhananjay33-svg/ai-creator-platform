"""A1 incremental CLI: comparison, 14 answers, audit, verdict — hermetic."""
from __future__ import annotations

from production.avatar_dataset_evaluator import incremental as inc
from production.avatar_dataset_evaluator.config import Config
from production.avatar_dataset_evaluator.coverage import (ClipCoverage,
                                                          CoverageConfig)
from production.avatar_dataset_evaluator.report import build_report
from production.avatar_dataset_evaluator.storage import write_sqlite

CCFG = CoverageConfig()


def _write_old(rec, path, n_acc=40):
    """A frontal-only old dataset (no profiles, no smiles) like A0 measured."""
    records = [rec(filename=f"old{i:03}.mp4", duration=30.0, expression="talking")
               for i in range(n_acc)]
    records += [rec(filename=f"oldrej{i:03}.mp4", accepted=False, quality="reject",
                    accept_reason="", reject_reason="no visible face")
                for i in range(10)]
    for i, r in enumerate(records, 1):
        r.id = i
    path.parent.mkdir(parents=True, exist_ok=True)
    write_sqlite(records, path)
    return records


def _new_records(rec):
    records = [
        rec(filename="n1.mp4", duration=60.0, expression="smiling"),
        rec(filename="n2.mp4", duration=90.0, face_view="left_profile",
            frontal_pct=30.0, profile_pct=70.0, expression="neutral"),
        rec(filename="n3.mp4", duration=90.0, face_view="right_profile",
            frontal_pct=30.0, profile_pct=70.0, expression="neutral"),
        rec(filename="n4.mp4", duration=45.0, expression="talking", speaking_pct=60.0),
        rec(filename="nrej.mp4", accepted=False, quality="reject", accept_reason="",
            reject_reason="heavy blur", motion_blur=5.0),
    ]
    for i, r in enumerate(records, 1):
        r.id = i
    return records


def test_answers_cover_all_14_questions(rec):
    old = [rec(filename=f"o{i}.mp4") for i in range(40)]
    old_rep = build_report(old)
    new = _new_records(rec)
    new_rep = build_report(new)
    merged_rep = build_report(old + new)
    covs = {"n1.mp4": ClipCoverage("n1.mp4", 10, 0.9, 0, 0, 0, 0, 0.5, False),
            "n2.mp4": ClipCoverage("n2.mp4", 10, 0.4, 0.4, 0, 0.3, 0, 0, False),
            "n3.mp4": ClipCoverage("n3.mp4", 10, 0.4, 0, 0.4, 0, 0.3, 0, False)}
    from production.avatar_dataset_evaluator.coverage import coverage_minutes
    cov_min = coverage_minutes(new, covs, CCFG)

    qa = inc.answer_questions(old_rep, new_rep, merged_rep, cov_min, True, CCFG)
    assert len(qa) == 14
    answers = dict(qa)
    assert answers["2. Did we recover Left views?"].startswith("YES")
    assert answers["3. Did we recover Right views?"].startswith("YES")
    assert answers["4. Did we recover Looking Up?"].startswith("YES")
    assert answers["5. Did we recover Looking Down?"].startswith("YES")
    assert answers["6. Did we recover Smiling?"].startswith("YES")
    assert answers["7. Did we recover Serious?"].startswith("YES")
    assert "/100" in answers["13. If merged, what will be the new Avatar Readiness Score?"]


def test_audit_passes_on_consistent_records(rec):
    text, ok = inc.audit(_new_records(rec), 30, seed=1, cfg=Config())
    assert ok
    assert "ACCEPTED sample (4): 4/4 pass" in text
    assert "REJECTED sample (1): 1/1" in text


def test_audit_fails_on_inconsistent_accept(rec):
    bad = [rec(filename="dark.mp4", lighting_mean=20.0)]     # accepted yet very dark
    _, ok = inc.audit(bad, 30, seed=1, cfg=Config())
    assert not ok


def test_end_to_end_skip_eval(tmp_path, rec, capsys, monkeypatch):
    out = tmp_path / "avatar_dataset_new"
    (out / "accepted").mkdir(parents=True)
    write_sqlite(_new_records(rec), out / "dataset.sqlite")
    _write_old(rec, tmp_path / "old" / "dataset.sqlite")
    monkeypatch.setattr(inc, "analyze_coverage",
                        lambda p, c: ClipCoverage(p.name, 10, 0.9, 0.3, 0.3,
                                                  0.3, 0.3, 0.5, True))

    rc = inc.run(["--source", str(tmp_path / "src"), "--out", str(out),
                  "--old", str(tmp_path / "old"), "--skip-eval",
                  "--sample-n", "30", "--seed", "1"])
    assert rc == 0
    text = capsys.readouterr().out
    for marker in ("Viewpoint coverage", "Comparison: Old Avatar Dataset",
                   "Random audit", "The 14 questions",
                   "12. Should these videos be merged", "FINAL VERDICT"):
        assert marker in text, marker
    assert ("READY TO MERGE" in text) or ("NEEDS MORE RECORDING" in text)
    assert (out / "reports" / "a1_evaluation.txt").exists()
    assert (out / "reports" / "a1_evaluation.json").exists()
