"""Generate standard-duration reference clips for the reference study.

Run inside the kokoro venv (the only engine validated on this machine):

    .venvs\\kokoro\\Scripts\\python.exe -m voice_engine.scripts.generate_reference_clips

Produces 10/20/30/60 s English clips (+ 20 s Hindi) under
voice_engine/datasets/reference_audio/synthetic/.

NOTE: these are SYNTHETIC speech clips (Kokoro af_heart / hf_alpha voices).
They exercise reference *acceptance mechanics* and give the similarity
metric a real target, but human-recorded references are still required for
production listening tests (see datasets/reference_audio/README.md).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants import Language  # noqa: E402
from foundation.logging import configure_logging, get_logger  # noqa: E402
from voice_engine.adapters.kokoro import KokoroAdapter  # noqa: E402
from voice_engine.interfaces import SynthesisRequest  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "datasets" / "reference_audio" / "synthetic"

_EN_TEXT = (
    "Welcome to Capital Greens, Raipur's newest integrated township on the Vidhan Sabha Road. "
    "Spread across thirty two acres, the township brings together residential towers, a high "
    "street retail zone, and a dedicated senior living block. The first three towers offer two "
    "and three bedroom residences ranging from one thousand fifty to eighteen hundred fifty "
    "square feet, with no shared walls and full height windows in every home. A two acre "
    "central park, an amphitheater, and a football turf anchor the open spaces, while the "
    "clubhouse hosts a gym, a swimming pool, and community halls for festivals. "
) * 4

_HI_TEXT = (
    "नमस्कार, कैपिटल ग्रीन्स में आपका स्वागत है। यह रायपुर की सबसे नई टाउनशिप है, जो बत्तीस एकड़ "
    "में फैली हुई है। यहाँ दो और तीन बीएचके के घर उपलब्ध हैं, और हर फ्लैट में हवा और रोशनी का "
    "पूरा इंतज़ाम है। टाउनशिप में सेंट्रल पार्क, क्लबहाउस और स्विमिंग पूल भी हैं। "
) * 3


def main() -> int:
    configure_logging()
    logger = get_logger("voice_engine.scripts.reference_clips")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    adapter = KokoroAdapter(device="cpu")

    # One long EN take, sliced to standard durations for a controlled study.
    long_path = OUTPUT_DIR / "en_full_take.wav"
    result = adapter.synthesize(
        SynthesisRequest(text=_EN_TEXT, language=Language.ENGLISH, output_path=long_path)
    )
    logger.info("EN take generated", extra={"context": {"s": round(result.audio_duration_s, 1)}})

    from foundation.shared_utils.audio_io import WavData, read_wav, write_wav
    wav = read_wav(long_path)
    for seconds in (10, 20, 30, 60):
        n = min(len(wav.samples), seconds * wav.sample_rate)
        clip = WavData(samples=wav.samples[:n], sample_rate=wav.sample_rate)
        out = write_wav(OUTPUT_DIR / f"synthetic_en_{seconds}s.wav", clip)
        print(f"wrote {out.name} ({clip.duration_s:.1f}s)")

    hi_path = OUTPUT_DIR / "synthetic_hi_20s.wav"
    result = adapter.synthesize(
        SynthesisRequest(text=_HI_TEXT, language=Language.HINDI, output_path=hi_path)
    )
    hi = read_wav(hi_path)
    if hi.duration_s > 20:
        write_wav(hi_path, WavData(samples=hi.samples[: 20 * hi.sample_rate],
                                   sample_rate=hi.sample_rate))
    print(f"wrote {hi_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
