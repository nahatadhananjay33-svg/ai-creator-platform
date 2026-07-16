"""CLI: validate the production dataset and emit the upload manifest (read-only).

    python -m production.cloud_setup.prepare
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .manifest import build_manifest, write_manifest

DEFAULT_DATASET = r"D:\AI_CREATOR_DATA\Tanshi\production_voice_dataset"
DEFAULT_OUT = Path("production/cloud_setup/manifest")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m production.cloud_setup.prepare",
                                 description="Validate + checksum the production voice dataset.")
    ap.add_argument("--dataset", default=DEFAULT_DATASET)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--no-progress", action="store_true")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    root = Path(args.dataset)
    if not root.is_dir():
        print(f"Dataset not found: {root}")
        return 1

    print(f"Dataset: {root}  (read-only)")
    man = build_manifest(root, progress=not args.no_progress)

    st, md = man["structure"], man["metadata"]
    print("\n-- structure --")
    print(f"  ok               : {st['ok']}")
    print(f"  missing dirs     : {st['missing_dirs'] or 'none'}")
    print(f"  missing metadata : {st['missing_metadata'] or 'none'}")
    print(f"  accepted / rejected wavs: {st['accepted_wavs']} / {st['rejected_wavs']}")
    print("-- metadata --")
    print(f"  ok               : {md['ok']}")
    print(f"  rows / accepted  : {md['rows']} / {md['accepted_rows']} "
          f"(on disk {md['accepted_on_disk']})")
    print(f"  missing on disk  : {md['missing_count']} | orphan files: {md['orphan_count']}")
    print(f"  accepted hours   : {md['accepted_hours']} (speech {md['accepted_speech_hours']})")
    print("-- manifest --")
    print(f"  files            : {man['file_count']}")
    print(f"  total size       : {man['total_mb']} MB")

    out = Path(args.out)
    j = write_manifest(man, out / "voice_dataset_manifest.json",
                       out / "voice_dataset_manifest.csv")
    print(f"\nWrote: {j}")
    print(f"       {out / 'voice_dataset_manifest.csv'}")
    return 0 if (st["ok"] and md["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
