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
from voice_engine.adapters.kokoro_g2p import EN_G2P_MODEL, ensure_en_core_web_sm  # noqa: E402
from voice_engine.interfaces import SynthesisRequest  # noqa: E402
from voice_engine.metrics import validate_kokoro_output  # noqa: E402
from avatar_engine.datasets import AvatarDatasetManager  # noqa: E402

logger = get_logger("avatar_engine.scripts.scenario_audio")


def main() -> int:
    configure_logging()
    manager = AvatarDatasetManager()
    dataset = manager.load()

    # Verify (and self-heal) the English G2P model BEFORE generating, so English
    # scenarios don't fail with spaCy [E050]. English is most scenarios.
    if any(s.language != "hi" for s in dataset.scenarios):
        try:
            already = ensure_en_core_web_sm()
            print(f"English G2P model {EN_G2P_MODEL}: "
                  f"{'present' if already else 'downloaded'}")
        except RuntimeError as exc:
            logger.error("English G2P model unavailable", extra={"context": {"error": str(exc)}})
            print(f"[FATAL] {exc}")
            return 2

    adapter = KokoroAdapter(device="cpu")
    manager.assets_dir.mkdir(parents=True, exist_ok=True)

    generated, failed = 0, []
    for scenario in dataset.scenarios:
        assets = manager.resolve_assets(scenario)
        target = assets.driving_audio
        language = Language.HINDI if scenario.language == "hi" else Language.ENGLISH
        try:
            result = adapter.synthesize(
                SynthesisRequest(text=scenario.script_text, language=language, output_path=target)
            )
        except Exception as exc:  # noqa: BLE001 - report the real Kokoro error, never fake audio
            logger.error("Kokoro synthesis failed",
                         extra={"context": {"scenario": scenario.scenario_id, "error": str(exc)}})
            print(f"[FAILED] {scenario.scenario_id}: Kokoro error: {exc}")
            failed.append(scenario.scenario_id)
            continue

        # Verify the file Kokoro produced is real speech (not silent/corrupted).
        v = validate_kokoro_output(target, expected_duration_s=scenario.target_duration_s)
        status = "OK" if v.valid else "INVALID"
        print(f"[{status}] {scenario.scenario_id}: {result.audio_duration_s:.1f}s -> "
              f"{target.name} ({v.audio_class})")
        if not v.valid:
            logger.error("Kokoro output failed validation",
                         extra={"context": {"scenario": scenario.scenario_id,
                                            "class": v.audio_class, "reason": v.reason}})
            failed.append(scenario.scenario_id)
        else:
            generated += 1

    print(f"\n{generated} valid speech files written to {manager.assets_dir}")
    if failed:
        print(f"{len(failed)} FAILED (no placeholder written): {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
