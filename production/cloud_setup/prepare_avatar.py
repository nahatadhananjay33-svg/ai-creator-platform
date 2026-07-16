"""CLI: validate the production AVATAR dataset and emit its upload manifest.

    python -m production.cloud_setup.prepare_avatar [--include-all]

Read-only; never modifies the dataset (the preparation pipeline is frozen).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from .avatar_manifest import build_avatar_manifest
from .manifest import write_manifest

DEFAULT_DATASET = r"D:\AI_CREATOR_DATA\Tanshi\avatar_dataset"
DEFAULT_OUT = Path("production/cloud_setup/manifest")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m production.cloud_setup.prepare_avatar",
        description="Validate + checksum the production avatar dataset.")
    ap.add_argument("--dataset", default=DEFAULT_DATASET)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--include-all", action="store_true",
                    help="also manifest rejected/cropped_src/_recovery (~+9.4 GB)")
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
    man = build_avatar_manifest(root, include_all=args.include_all,
                                progress=not args.no_progress)

    st, md = man["structure"], man["metadata"]
    print("\n-- structure --")
    print(f"  ok               : {st['ok']}")
    print(f"  missing dirs     : {st['missing_dirs'] or 'none'}")
    print(f"  missing metadata : {st['missing_metadata'] or 'none'}")
    print(f"  accepted / rejected clips: {st['accepted_files']} / {st['rejected_files']}")
    print("-- metadata --")
    print(f"  ok               : {md['ok']}")
    print(f"  rows / accepted  : {md['rows']} / {md['accepted_rows']} "
          f"(on disk {md['accepted_on_disk']})")
    print(f"  missing on disk  : {md['missing_count']} | orphan files: {md['orphan_count']}")
    print(f"  accepted minutes : {md['accepted_minutes']}")
    print(f"  provenance       : {md['provenance']}")
    print("-- manifest --")
    print(f"  upload scope     : {man['upload_scope']}")
    print(f"  files            : {man['file_count']}")
    print(f"  total size       : {man['total_gb']} GB")

    out = Path(args.out)
    j = write_manifest(man, out / "avatar_dataset_manifest.json",
                       out / "avatar_dataset_manifest.csv")
    print(f"\nWrote: {j}")
    print(f"       {out / 'avatar_dataset_manifest.csv'}")
    return 0 if (st["ok"] and md["ok"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
