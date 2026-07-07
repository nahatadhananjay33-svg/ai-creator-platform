"""Permanent MuseTalk GPU smoke test (Phase A4.5).

Single-command, end-to-end validation of an installed MuseTalk environment:
checks the GPU/CUDA runtime and that the adapter + weights are present, then
runs the *smallest possible* inference — one demo portrait + ~1 s of audio
(≈25 frames) — and confirms the produced mp4 actually decodes. This is the
canonical GPU check to run after any future install.

    python avatar_engine/scripts/smoke_musetalk.py
    python -m avatar_engine.scripts.smoke_musetalk --device cuda

It reuses the real ``MuseTalkAdapter`` (same code path as the benchmark), the
weight manifest, and ``probe_video`` — no bespoke inference logic.

Exit codes:
    0  success — GPU inference produced a readable mp4
    1  prerequisites missing (repo/weights not installed, imports fail, or CUDA
       unavailable) → run ``install_models --models musetalk``
    2  demo assets missing from the cloned MuseTalk repo
    3  inference ran but produced no readable video
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.logging import configure_logging  # noqa: E402
from foundation.model_manager.installer import REPOS_DIR  # noqa: E402
from avatar_engine.models.interface import GenerationRequest  # noqa: E402
from avatar_engine.models.media import probe_video  # noqa: E402
from avatar_engine.models.musetalk import MuseTalkAdapter  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "smoke"
#: Smallest demo portrait shipped in the MuseTalk repo (474x266).
_DEMO_PORTRAIT = "assets/demo/musk/musk.png"
#: Demo audio shipped in the repo; trimmed to keep the inference tiny.
_DEMO_AUDIO = "data/audio/yongen.wav"


class SmokeError(Exception):
    """Prerequisite/asset failure carrying a user-facing message + exit code."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def _prepare_audio(src: Path, seconds: float, work_dir: Path) -> Path:
    """Trim ``src`` to its first ``seconds`` to keep the inference minimal.

    Falls back to the full clip if soundfile is unavailable or trimming fails —
    the smoke test still runs, just on a longer clip.
    """
    try:
        import soundfile as sf

        data, sr = sf.read(str(src))
        n = max(1, int(sr * seconds))
        if len(data) <= n:
            return src
        work_dir.mkdir(parents=True, exist_ok=True)
        dst = work_dir / f"smoke_{seconds:g}s.wav"
        sf.write(str(dst), data[:n], sr)
        return dst
    except Exception:  # noqa: BLE001 - trimming is a best-effort optimization
        return src


def resolve_inputs(repo_dir: Path, seconds: float, work_dir: Path) -> tuple[Path, Path]:
    """Locate the demo portrait + (trimmed) driving audio in the cloned repo.

    Raises :class:`SmokeError` (code 2) naming any missing asset.
    """
    portrait = repo_dir / _DEMO_PORTRAIT
    audio_src = repo_dir / _DEMO_AUDIO
    missing = [p for p in (portrait, audio_src) if not p.exists()]
    if missing:
        raise SmokeError(
            "MuseTalk demo assets not found: "
            + ", ".join(str(p) for p in missing)
            + " (expected in the cloned repo — re-run the installer)",
            code=2,
        )
    return portrait, _prepare_audio(audio_src, seconds, work_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MuseTalk GPU smoke test")
    parser.add_argument("--repo-dir", default=str(REPOS_DIR / "musetalk"))
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--device", default="cuda", choices=["cuda", "auto"],
                        help="Device to request (default: cuda — this is a GPU test)")
    parser.add_argument("--audio-seconds", type=float, default=1.0,
                        help="Trim driving audio to this many seconds (default: 1.0)")
    args = parser.parse_args(argv)
    configure_logging()

    repo_dir = Path(args.repo_dir)
    out_dir = Path(args.output_dir)
    adapter = MuseTalkAdapter(device=args.device, config={"repo_dir": repo_dir})

    # 1) Cheap on-disk prerequisite check (no venv): repo entrypoint + weights.
    missing_paths = [p for p in adapter.required_paths() if not p.exists()]
    if missing_paths:
        print("FAIL: MuseTalk is not installed — missing repo entrypoint / weights:")
        for p in missing_paths:
            print(f"  - {p}")
        print("Fix: python -m avatar_engine.scripts.install_models --models musetalk")
        return 1

    # 2) Runtime diagnostics inside the model venv: imports + GPU/CUDA.
    diag = adapter.diagnostics(force=True)
    print(f"GPU device      : {diag.cuda_device_name or 'none detected'}")
    print(f"CUDA available  : {diag.torch_cuda_available}")
    print(f"Torch           : {diag.torch_version} (cuda build {diag.torch_cuda_build})")
    print(f"Environment     : {'ready' if diag.available else 'NOT ready'} — {diag.reason}")
    if not diag.available:
        print(f"FAIL: MuseTalk environment not ready: {diag.reason}")
        return 1
    if not diag.torch_cuda_available:
        print("FAIL: a CUDA GPU is required but torch.cuda.is_available() is False "
              "in the MuseTalk venv.")
        return 1

    # 3) Smallest inference: demo portrait + ~1 s audio.
    try:
        image, audio = resolve_inputs(repo_dir, args.audio_seconds, out_dir / "work")
    except SmokeError as exc:
        print(f"FAIL: {exc}")
        return exc.code

    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "musetalk_smoke.mp4"
    print(f"Inference       : {image.name} + {audio.name} "
          f"({args.audio_seconds:g}s) -> {output_path.name} ...")
    try:
        result = adapter.generate(
            GenerationRequest(source_image=image, driving_audio=audio,
                              output_path=output_path)
        )
    except Exception as exc:  # noqa: BLE001 - surface any inference failure cleanly
        print(f"FAIL: MuseTalk inference failed: {exc}")
        return 3

    # 4) Validate the produced mp4 actually decodes.
    try:
        probe = probe_video(result.video_path)
    except Exception as exc:  # noqa: BLE001 - unreadable output is a failure
        print(f"FAIL: output video not decodable: {exc}")
        return 3
    if not (result.video_path.exists() and probe.readable):
        print(f"FAIL: output missing or not decodable: {result.video_path}")
        return 3

    print("")
    print("=== MuseTalk GPU smoke test PASSED ===")
    print(f"output          : {result.video_path} ({result.video_path.stat().st_size} bytes)")
    print(f"video           : {probe.width}x{probe.height} @ {probe.fps}fps, "
          f"{probe.frame_count} frames, {probe.duration_s}s")
    print(f"device_actual   : {result.metadata.get('device_actual')}")
    print(f"generation_time : {round(result.generation_time_s, 1)}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
