"""Permanent Chatterbox GPU smoke test (Phase B2.2).

Single-command, end-to-end validation of an installed Chatterbox environment —
the Voice-Engine GPU analogue of ``smoke_kokoro.py`` (CPU) and the Avatar
Engine's ``smoke_latentsync.py``. Chatterbox is a 0.5B autoregressive cloner
that is not CPU-real-time, so this is a **GPU** test by default: it checks the
adapter is importable and CUDA is live, then clones a short line per language
through the real ``ChatterboxAdapter`` (same code path as production), confirms
each WAV decodes, and reports device / CUDA / VRAM / startup / inference / RTF —
the numbers the benchmark tracks.

Cloning needs a reference clip, and the human reference set is gitignored, so
the smoke test synthesizes its own **self-contained** synthetic reference
(a voice-like multi-harmonic tone) — enough to exercise the voice encoder + the
full generate() path. Quality is not asserted here (that is the reference-study
job); readability and the GPU path are.

    .venvs/chatterbox/bin/python voice_engine/scripts/smoke_chatterbox.py
    .venvs/chatterbox/bin/python voice_engine/scripts/smoke_chatterbox.py --languages en

Exit codes:
    0  success — every requested language produced a readable, non-trivial WAV
    1  prerequisites missing (chatterbox not installed) or CUDA unavailable when
       requested → run ``install_models --models chatterbox``
    3  inference ran but produced no readable audio
"""
from __future__ import annotations

import argparse
import array
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants import Language  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import Stopwatch, WavData, read_wav, write_wav  # noqa: E402
from voice_engine.adapters.chatterbox import ChatterboxAdapter  # noqa: E402
from voice_engine.interfaces import SynthesisRequest  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "smoke"

#: Short one-liners kept minimal so the smoke run is fast. Devanagari for Hindi
#: so Chatterbox's multilingual tokenizer resolves the 'hi' path directly.
_DEMO_TEXT = {
    Language.ENGLISH: "Welcome to Capital Greens. How can I help you today?",
    Language.HINDI: "नमस्ते, कैपिटल ग्रीन्स में आपका स्वागत है।",
}
_LANG = {"en": Language.ENGLISH, "hi": Language.HINDI}

#: Synthetic reference length — above the adapter's 7.0 s ``min_reference_audio_s``
#: floor so ``create_voice_profile`` accepts it.
_REF_SECONDS = 8.0


def _synthetic_reference(path: Path, seconds: float = _REF_SECONDS,
                         sample_rate: int = 24_000) -> Path:
    """Write a self-contained, voice-like reference WAV (stdlib only).

    A fundamental + two harmonics with slow amplitude modulation (a crude
    voiced-speech envelope). Peak sits well inside int16 so it passes
    ``validate_reference`` (not clipped, not near-silent). This is NOT a real
    voice — it only exercises the encoder + generate() path for the smoke check.
    """
    n = int(seconds * sample_rate)
    f0 = 130.0  # fundamental in a speech-like range
    peak = int(0.5 * 32767)
    samples = array.array("h")
    for i in range(n):
        t = i / sample_rate
        env = 0.6 + 0.4 * math.sin(2.0 * math.pi * 3.0 * t)  # 3 Hz syllable-rate AM
        s = (math.sin(2 * math.pi * f0 * t)
             + 0.5 * math.sin(2 * math.pi * 2 * f0 * t)
             + 0.3 * math.sin(2 * math.pi * 3 * f0 * t))
        samples.append(int(max(-1.0, min(1.0, env * s / 1.8)) * peak))
    write_wav(path, WavData(samples=samples, sample_rate=sample_rate, channels=1))
    return path


def _torch_report() -> dict:
    """CUDA/torch facts from inside the venv (best-effort; empty if no torch)."""
    try:
        import torch  # type: ignore[import-not-found]

        info = {"torch": torch.__version__, "cuda_build": torch.version.cuda,
                "cuda_available": torch.cuda.is_available()}
        if torch.cuda.is_available():
            info["device_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["total_vram_gb"] = round(props.total_memory / (1024**3), 2)
        return info
    except Exception:  # noqa: BLE001 - torch reporting is best-effort
        return {}


def _peak_vram_gb() -> float:
    try:
        import torch  # type: ignore[import-not-found]

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024**3), 2)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def _model_device(adapter: ChatterboxAdapter) -> str:
    """The model's actual inference device (not just what was requested)."""
    dev = getattr(adapter._model, "device", None)  # noqa: SLF001 - diagnostic read
    return str(dev) if dev is not None else "unknown"


def _synthesize(adapter: ChatterboxAdapter, language: Language, text: str,
                voice, out_path: Path) -> dict:
    """Run one clone+synthesis and return its measured row."""
    with Stopwatch() as sw:
        adapter.synthesize(
            SynthesisRequest(text=text, language=language, voice=voice,
                             output_path=out_path)
        )
    wav = read_wav(out_path)
    synth_s = sw.elapsed_s
    rtf = synth_s / wav.duration_s if wav.duration_s > 0 else float("inf")
    return {"synth_s": synth_s, "audio_s": wav.duration_s, "rtf": rtf,
            "sample_rate": wav.sample_rate, "readable": wav.duration_s > 0.05}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chatterbox GPU smoke test")
    parser.add_argument("--languages", nargs="+", default=["en", "hi"],
                        choices=["en", "hi"])
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu", "auto"],
                        help="Device to request (default: cuda — this is a GPU test)")
    parser.add_argument("--repeats", type=int, default=1,
                        help="Warm repeats per language after the cold run (default: 1)")
    args = parser.parse_args(argv)
    configure_logging()

    out_dir = Path(args.output_dir)
    adapter = ChatterboxAdapter(device=args.device)

    # 1) Prerequisite check: the adapter's import must be present.
    if not adapter.is_available():
        print("FAIL: Chatterbox is not installed — the `chatterbox` package is missing.")
        print("Fix: python -m voice_engine.scripts.install_models --models chatterbox")
        return 1

    # 2) GPU/CUDA diagnostics (this is a GPU test — surface the runtime honestly).
    tr = _torch_report()
    print(f"Torch           : {tr.get('torch', '?')} (cuda build {tr.get('cuda_build')})")
    print(f"CUDA available  : {tr.get('cuda_available')}")
    print(f"GPU device      : {tr.get('device_name', 'none detected')}")
    if "total_vram_gb" in tr:
        print(f"GPU total VRAM  : {tr['total_vram_gb']} GB")
    if args.device == "cuda" and not tr.get("cuda_available"):
        print("FAIL: --device cuda requested but torch.cuda.is_available() is False "
              "in the Chatterbox venv. Reinstall with a GPU host, or pass --device cpu.")
        return 1

    # 3) Build the self-contained synthetic reference + a voice profile.
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_path = _synthetic_reference(out_dir / "chatterbox_reference.wav")
    try:
        voice = adapter.create_voice_profile(ref_path, display_name="smoke-synthetic")
    except Exception as exc:  # noqa: BLE001 - reference rejection is a setup failure
        print(f"FAIL: synthetic reference rejected: {exc}")
        return 3

    # 4) Adapter load (weights + codec — the real Chatterbox cold-start cost).
    with Stopwatch() as sw:
        adapter.load()
    load_s = sw.elapsed_s
    print(f"Device requested: {args.device}")
    print(f"Model device    : {_model_device(adapter)}")
    print(f"Adapter load    : {round(load_s, 2)}s")

    rows: list[dict] = []
    for code in args.languages:
        language = _LANG[code]
        text = _DEMO_TEXT[language]
        out_path = out_dir / f"chatterbox_smoke_{code}.wav"
        try:
            cold = _synthesize(adapter, language, text, voice, out_path)
            warm = [_synthesize(adapter, language, text, voice, out_path)
                    for _ in range(max(0, args.repeats))]
        except Exception as exc:  # noqa: BLE001 - surface any inference failure cleanly
            print(f"FAIL: Chatterbox inference failed for {code}: {exc}")
            return 3
        if not cold["readable"]:
            print(f"FAIL: Chatterbox produced no readable audio for {code}: {out_path}")
            return 3
        warm_rtf = sum(w["rtf"] for w in warm) / len(warm) if warm else cold["rtf"]
        rows.append({"lang": code, "cold_s": cold["synth_s"], "cold_rtf": cold["rtf"],
                     "warm_rtf": warm_rtf, "audio_s": cold["audio_s"],
                     "sr": cold["sample_rate"], "path": out_path})

    peak_vram = _peak_vram_gb()
    print("")
    print("=== Chatterbox GPU smoke test PASSED ===")
    print(f"{'lang':4} {'cold_s':>8} {'cold_RTF':>9} {'warm_RTF':>9} "
          f"{'audio_s':>8}  output")
    for r in rows:
        print(f"{r['lang']:4} {r['cold_s']:8.2f} {r['cold_rtf']:9.3f} "
              f"{r['warm_rtf']:9.3f} {r['audio_s']:8.2f}  "
              f"{r['path'].name} ({r['sr']} Hz)")
    print("")
    print(f"startup (load)  : {round(load_s, 2)}s")
    print(f"peak VRAM       : {peak_vram} GB (torch.cuda.max_memory_allocated)")
    print(f"reference       : {ref_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
