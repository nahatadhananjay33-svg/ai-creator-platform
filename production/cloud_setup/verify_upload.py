"""CLI: verify an uploaded dataset copy against the manifest.

Works locally or on Colab against a mounted Drive folder:

    python -m production.cloud_setup.verify_upload --target "/content/drive/MyDrive/.../production_voice_dataset"
    python -m production.cloud_setup.verify_upload --target <dir> --quick   # presence+size only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .manifest import load_manifest, verify_against

DEFAULT_MANIFEST = "production/cloud_setup/manifest/voice_dataset_manifest.json"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m production.cloud_setup.verify_upload",
                                 description="Verify an uploaded dataset copy against the manifest.")
    ap.add_argument("--target", required=True, help="uploaded dataset root (e.g. Drive mount)")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--quick", action="store_true", help="presence+size only (skip sha256)")
    ap.add_argument("--report", default=None, help="write a JSON report here")
    ap.add_argument("--no-progress", action="store_true")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    mpath = Path(args.manifest)
    if not mpath.exists():
        print(f"Manifest not found: {mpath}  (run: python -m production.cloud_setup.prepare)")
        return 1
    man = load_manifest(mpath)
    target = Path(args.target)
    if not target.is_dir():
        print(f"Target not found: {target}")
        return 1

    res = verify_against(man, target, quick=args.quick, progress=not args.no_progress)
    print(f"\nTarget   : {res['target_root']}  ({'quick' if res['quick'] else 'full sha256'})")
    print(f"Expected : {res['expected_files']} files")
    print(f"Verified : {res['verified']}")
    print(f"Missing  : {res['missing_count']}")
    print(f"Size bad : {res['size_mismatch_count']}")
    print(f"Hash bad : {res['hash_mismatch_count']}")
    print(f"RESULT   : {'PASS - upload matches the manifest' if res['ok'] else 'FAIL - see lists below'}")
    for label, key in (("missing", "missing"), ("size mismatch", "size_mismatch"),
                       ("hash mismatch", "hash_mismatch")):
        if res[key]:
            print(f"  first {label}: {res[key][:10]}")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"\nReport: {args.report}")
    return 0 if res["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
