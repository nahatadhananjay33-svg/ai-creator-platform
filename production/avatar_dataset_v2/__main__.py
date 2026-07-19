"""Avatar dataset v2 optimizer - full run.

    python -m production.avatar_dataset_v2

Stages (all resume-safe; rerun after interruption and it continues):
  1. detect + crop-solve + master render (1280) per clip, in parallel
  2. encode 1024/768 variants from the master, place accepted/rejected
  3. per-variant artifacts, winner pick, thumbnails, comparison sheets,
     top-level avatar_dataset_v2 assembly + upgrade report
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from .config import (DEFAULT_RES, OUT_ROOT, RENDER_DIR, RENDER_RES,
                     RESOLUTIONS, RUN, STATE_DIR, VARIANT_ROOT, source_clips)
from .metrics import pick_winner, score_variant, variant_row, write_artifacts
from .render import process_clip
from .reports import (make_comparison_sheets, make_thumbnails,
                      write_upgrade_report)


def stage1_render(clips) -> list[dict]:
    todo = []
    states = []
    for c in clips:
        from .config import safe_stem
        st = STATE_DIR / f"{safe_stem(c.name)}.json"
        master = RENDER_DIR / f"{safe_stem(c.name)}.mp4"
        if st.exists() and (master.exists() and master.stat().st_size > 0
                            or json.loads(st.read_text(encoding='utf-8')).get("status") == "failed"):
            states.append(json.loads(st.read_text(encoding="utf-8")))
        else:
            todo.append(c)
    print(f"[stage1] {len(states)} done, {len(todo)} to process "
          f"({RUN.workers} workers)")
    if todo:
        with ProcessPoolExecutor(max_workers=RUN.workers) as pool:
            futs = {pool.submit(process_clip, c): c for c in todo}
            for i, fut in enumerate(as_completed(futs), 1):
                try:
                    st = fut.result()
                except Exception as e:  # keep going; clip marked on next run
                    print(f"[stage1] ERROR {futs[fut].name}: {e}", flush=True)
                    continue
                states.append(st)
                if i % 10 == 0 or i == len(todo):
                    print(f"[stage1] {i}/{len(todo)} "
                          f"(last: {st['stem']} {st['status']})", flush=True)
    return states


def _encode_variant(master: Path, dest: Path, res: int) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    if res == RENDER_RES:
        try:
            os.link(master, dest)
        except OSError:
            shutil.copyfile(master, dest)
        return True
    tmp = dest.with_suffix(".tmp.mp4")
    rc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(master),
         "-vf", f"scale={res}:{res}", "-c:v", "libx264", "-crf", str(RUN.crf),
         "-preset", RUN.preset, "-pix_fmt", "yuv420p", "-c:a", "copy",
         str(tmp)]).returncode
    if rc == 0 and tmp.exists() and tmp.stat().st_size > 0:
        tmp.replace(dest)
        return True
    tmp.unlink(missing_ok=True)
    return False


def stage2_variants(states) -> dict[int, list[dict]]:
    rows_by_res: dict[int, list[dict]] = {r: [] for r in RESOLUTIONS}
    rendered = [s for s in states if s.get("status") == "rendered"]
    jobs = []
    for res in RESOLUTIONS:
        for st in states:
            row = variant_row(st, res)
            rows_by_res[res].append(row)
            if st.get("status") != "rendered":
                continue
            sub = "accepted" if row["accepted"] else "rejected"
            dest = VARIANT_ROOT[res] / sub / f"{st['stem']}.mp4"
            jobs.append((RENDER_DIR / f"{st['stem']}.mp4", dest, res))
    print(f"[stage2] encoding/placing {len(jobs)} variant files...")
    with ProcessPoolExecutor(max_workers=RUN.workers) as pool:
        futs = [pool.submit(_encode_variant, *j) for j in jobs]
        done = sum(f.result() for f in as_completed(futs))
    print(f"[stage2] {done}/{len(jobs)} variant files in place")
    return rows_by_res


def stage3_reports(states, rows_by_res) -> None:
    scores = {}
    for res in RESOLUTIONS:
        root = VARIANT_ROOT[res]
        (root / "reports").mkdir(parents=True, exist_ok=True)
        write_artifacts(root, rows_by_res[res])
        scores[res] = score_variant(root)
    winner = pick_winner(scores)
    print(f"[stage3] winner variant: {winner}px "
          f"({scores[winner]['accepted']} accepted, "
          f"avg face {scores[winner]['face_avg_mean']:.0f}px)")

    # top-level dataset = the winner variant, plus shared visual reports
    for sub in ("accepted", "rejected"):
        dest = OUT_ROOT / sub
        dest.mkdir(parents=True, exist_ok=True)
        for f in (VARIANT_ROOT[winner] / sub).glob("*.mp4"):
            t = dest / f.name
            if not t.exists():
                try:
                    os.link(f, t)
                except OSError:
                    shutil.copyfile(f, t)
    for name in ("dataset.csv", "dataset.xlsx", "dataset.sqlite",
                 "dataset_report.json"):
        src = VARIANT_ROOT[winner] / name
        if src.exists():
            shutil.copyfile(src, OUT_ROOT / name)

    make_thumbnails(states, OUT_ROOT / "thumbnails")
    n = make_comparison_sheets(states, OUT_ROOT / "comparison",
                               RUN.comparison_samples)
    write_upgrade_report(states, scores, winner, OUT_ROOT)
    (OUT_ROOT / "reports" / "variant_scores.json").write_text(
        json.dumps({"winner": winner, "scores": scores}, indent=2),
        encoding="utf-8")
    print(f"[stage3] artifacts + {n} comparison sheets written to {OUT_ROOT}")


def main() -> int:
    clips = source_clips()
    if not clips:
        print("no source clips found"); return 1
    for d in (STATE_DIR, RENDER_DIR, OUT_ROOT / "reports"):
        d.mkdir(parents=True, exist_ok=True)
    print(f"avatar_dataset_v2 optimizer: {len(clips)} source clips, "
          f"variants {RESOLUTIONS}, default {DEFAULT_RES}")
    states = stage1_render(clips)
    rows = stage2_variants(states)
    stage3_reports(states, rows)
    rendered = sum(1 for s in states if s.get("status") == "rendered")
    print(f"DONE: {rendered}/{len(states)} rendered; see "
          f"{OUT_ROOT / 'dataset_upgrade_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
