"""Permanent Kokoro CPU smoke test (Phase B2.1).

Single-command, end-to-end validation of an installed Kokoro environment — the
voice-engine analogue of the Avatar Engine's ``smoke_musetalk.py`` /
``smoke_latentsync.py``. Kokoro is CPU-real-time, so this is a **CPU** test by
default (no GPU, no Colab): it checks the adapter is importable, then synthesizes
one short line per language through the real ``KokoroAdapter`` (same code path as
production), confirms each WAV decodes, and reports startup / inference / RTF /
memory — the numbers the benchmark tracks.

    python voice_engine/scripts/smoke_kokoro.py
    .venvs/kokoro/bin/python voice_engine/scripts/smoke_kokoro.py --languages en hi

Exit codes:
    0  success — every requested language produced a readable, non-trivial WAV
    1  prerequisites missing (kokoro not installed) → run
       ``install_models --models kokoro``
    3  inference ran but produced no readable audio
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants import Language  # noqa: E402
from foundation.logging import configure_logging  # noqa: E402
from foundation.shared_utils import Stopwatch, read_wav  # noqa: E402
from voice_engine.adapters.kokoro import KokoroAdapter  # noqa: E402
from voice_engine.interfaces import SynthesisRequest  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "output" / "smoke"

#: Short one-liners kept minimal so the smoke run is fast. Devanagari for Hindi
#: so Kokoro's Hindi G2P ('h') resolves without romanization ambiguity.
_DEMO_TEXT = {
    Language.ENGLISH: "Welcome to Capital Greens. How can I help you today?",
    Language.HINDI: "नमस्ते, कैपिटल ग्रीन्स में आपका स्वागत है।",
}
_LANG = {"en": Language.ENGLISH, "hi": Language.HINDI}


def _rss_mb() -> float:
    """Resident set size in MB (best-effort; 0.0 if psutil is unavailable)."""
    try:
        import psutil  # type: ignore[import-not-found]

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001 - memory reporting is best-effort
        return 0.0


def _synthesize(adapter: KokoroAdapter, language: Language, text: str,
                out_path: Path) -> dict:
    """Run one synthesis and return its measured row."""
    with Stopwatch() as sw:
        adapter.synthesize(
            SynthesisRequest(text=text, language=language, output_path=out_path)
        )
    wav = read_wav(out_path)
    synth_s = sw.elapsed_s
    rtf = synth_s / wav.duration_s if wav.duration_s > 0 else float("inf")
    return {"synth_s": synth_s, "audio_s": wav.duration_s, "rtf": rtf,
            "sample_rate": wav.sample_rate, "readable": wav.duration_s > 0.05}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kokoro CPU smoke test")
    parser.add_argument("--languages", nargs="+", default=["en", "hi"],
                        choices=["en", "hi"])
    parser.add_argument("--output-dir", default=str(OUT_DIR))
    parser.add_argument("--device", default="cpu", choices=["cpu", "auto"],
                        help="Device to request (default: cpu — Kokoro is CPU-real-time)")
    parser.add_argument("--repeats", type=int, default=2,
                        help="Warm repeats per language after the cold run (default: 2)")
    args = parser.parse_args(argv)
    configure_logging()

    out_dir = Path(args.output_dir)
    adapter = KokoroAdapter(device=args.device)

    # 1) Prerequisite check: the adapter's import must be present.
    if not adapter.is_available():
        print("FAIL: Kokoro is not installed — the `kokoro` package is missing.")
        print("Fix: python -m voice_engine.scripts.install_models --models kokoro")
        return 1

    rss_start = _rss_mb()
    # 2) Adapter load (cheap for Kokoro; real cost is the first pipeline build).
    with Stopwatch() as sw:
        adapter.load()
    load_s = sw.elapsed_s

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Device          : {args.device}")
    print(f"Adapter load    : {round(load_s, 3)}s")

    rows: list[dict] = []
    peak_rss = rss_start
    for code in args.languages:
        language = _LANG[code]
        text = _DEMO_TEXT[language]
        out_path = out_dir / f"kokoro_smoke_{code}.wav"
        try:
            # Cold run: first synthesis for this language builds the KPipeline
            # (and downloads weights on a fresh install) — the true startup cost.
            cold = _synthesize(adapter, language, text, out_path)
            peak_rss = max(peak_rss, _rss_mb())
            warm = [_synthesize(adapter, language, text, out_path)
                    for _ in range(max(0, args.repeats))]
            peak_rss = max(peak_rss, _rss_mb())
        except Exception as exc:  # noqa: BLE001 - surface any inference failure cleanly
            print(f"FAIL: Kokoro inference failed for {code}: {exc}")
            return 3
        if not cold["readable"]:
            print(f"FAIL: Kokoro produced no readable audio for {code}: {out_path}")
            return 3
        warm_rtf = sum(w["rtf"] for w in warm) / len(warm) if warm else cold["rtf"]
        chars_per_s = len(text) / (warm[-1]["synth_s"] if warm else cold["synth_s"])
        rows.append({"lang": code, "cold_s": cold["synth_s"], "cold_rtf": cold["rtf"],
                     "warm_rtf": warm_rtf, "audio_s": cold["audio_s"],
                     "chars_per_s": chars_per_s, "sr": cold["sample_rate"],
                     "path": out_path})

    print("")
    print("=== Kokoro CPU smoke test PASSED ===")
    print(f"{'lang':4} {'cold_s':>8} {'cold_RTF':>9} {'warm_RTF':>9} "
          f"{'audio_s':>8} {'chars/s':>8}  output")
    for r in rows:
        print(f"{r['lang']:4} {r['cold_s']:8.2f} {r['cold_rtf']:9.3f} "
              f"{r['warm_rtf']:9.3f} {r['audio_s']:8.2f} {r['chars_per_s']:8.1f}  "
              f"{r['path'].name} ({r['sr']} Hz)")
    print("")
    print(f"startup (load)  : {round(load_s, 3)}s")
    print(f"peak RSS        : {round(peak_rss, 1)} MB (start {round(rss_start, 1)} MB)")
    realtime = all(r["warm_rtf"] < 1.0 for r in rows)
    print(f"CPU real-time   : {'YES (all warm RTF < 1.0)' if realtime else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
