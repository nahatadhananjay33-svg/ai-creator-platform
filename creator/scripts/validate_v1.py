"""Version 1.0 acceptance check (Phase C19).

Proves the stop condition end to end: a single command turns a prompt into a
reel that passes the quality gate and produces upload-ready metadata.

    python -m creator.scripts.validate_v1

Hermetic by default (mock renderer into a temporary workspace: no GPU, no
FFmpeg, no network). Exit 0 = ACCEPTED, exit 1 = REJECTED.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from creator import VERSION
from creator.config import load_creator_config
from creator.run import run


def validate(prompt: str = "Why investing in real estate early is beneficial",
             template: str = "real_estate") -> bool:
    with tempfile.TemporaryDirectory(prefix="creator_v1_") as tmp:
        ws_root = Path(tmp) / "workspace"
        cfg = load_creator_config(overrides={
            "generation": {"prompt": prompt, "template": template,
                           "renderer": "mock", "profiles": ["reel_9x16", "square_1x1"]},
            "quality": {"gate": True},
            "paths": {"root": str(ws_root)},
        })

        print(f"AI Creator Platform — Version {VERSION} acceptance check")
        print(f'  prompt   : "{prompt}"  (template: {template}, renderer: mock)\n')

        # One command: prompt -> workflow -> quality gate -> upload metadata.
        # With the quality gate ON, exit code 0 means the reel PASSED quality
        # *and* complete metadata was written.
        code = run(cfg, quiet=True)

        from creator.paths import resolve_workspace
        exports = resolve_workspace(str(ws_root)).exports / "why-investing-in-real-estate-early-is-beneficial"
        metadata_json = exports / "metadata.json"
        preview_md = exports / "upload_preview.md"
        renditions = list(exports.glob("*.avi")) + list(exports.glob("*.mp4"))

        checks: list[tuple[str, bool]] = [
            ("single command finished (quality PASS + metadata)", code == 0),
            ("metadata.json written", metadata_json.is_file()),
            ("upload_preview.md written", preview_md.is_file()),
            ("finished renditions bundled", len(renditions) >= 1),
        ]

        meta_ok = False
        if metadata_json.is_file():
            data = json.loads(metadata_json.read_text(encoding="utf-8"))
            meta_ok = bool(data.get("youtube_title")) and bool(data.get("hashtags"))
        checks.append(("metadata has title + hashtags", meta_ok))

        for label, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

        accepted = all(ok for _, ok in checks)
        print(f"\n=== VERSION 1.0 VALIDATION: {'ACCEPTED' if accepted else 'REJECTED'} ===")
        return accepted


def main() -> int:
    return 0 if validate() else 1


if __name__ == "__main__":
    raise SystemExit(main())
