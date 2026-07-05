"""Generate real driving audio for every avatar benchmark scenario.

Run inside the kokoro venv (the voice engine's validated CPU model):

    .venvs\\kokoro\\Scripts\\python.exe -m avatar_engine.scripts.generate_scenario_audio

Synthesizes each scenario's script with the platform Voice Engine adapter
(EN: af_heart, HI: hf_alpha) into avatar_engine/datasets/data/assets/
<scenario_id>.wav — real speech, so avatar lip-sync benchmarks measure
against actual phonemes instead of placeholder sine tones.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants import Language  # noqa: E402
from foundation.logging import configure_logging, get_logger  # noqa: E402
from voice_engine.adapters.kokoro import KokoroAdapter  # noqa: E402
from voice_engine.interfaces import SynthesisRequest  # noqa: E402
from avatar_engine.datasets import AvatarDatasetManager  # noqa: E402

logger = get_logger("avatar_engine.scripts.scenario_audio")


def main() -> int:
    configure_logging()
    manager = AvatarDatasetManager()
    dataset = manager.load()
    adapter = KokoroAdapter(device="cpu")
    manager.assets_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    for scenario in dataset.scenarios:
        assets = manager.resolve_assets(scenario)
        target = assets.driving_audio
        language = Language.HINDI if scenario.language == "hi" else Language.ENGLISH
        result = adapter.synthesize(
            SynthesisRequest(text=scenario.script_text, language=language, output_path=target)
        )
        logger.info(
            "Scenario audio generated",
            extra={"context": {"scenario": scenario.scenario_id,
                               "seconds": round(result.audio_duration_s, 1)}},
        )
        print(f"{scenario.scenario_id}: {result.audio_duration_s:.1f}s -> {target.name}")
        generated += 1
    print(f"\n{generated} scenario audio files written to {manager.assets_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
