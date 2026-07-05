"""Install voice models into isolated venvs and report results.

    python -m voice_engine.scripts.install_models --models kokoro f5-tts
    python -m voice_engine.scripts.install_models --all --report-only

Thin wrapper over the shared foundation install CLI (Phase A3.5 moved the
driver to foundation.model_manager.install_cli so voice and avatar share
one implementation). Reports land in voice_engine/output/installs/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.constants.paths import VOICE_ENGINE_DIR  # noqa: E402
from foundation.model_manager.install_cli import run_install_cli  # noqa: E402
from foundation.model_manager.spec import ModelSpec  # noqa: E402
from voice_engine.adapters.registry import ADAPTER_CLASSES  # noqa: E402
from voice_engine.models.install_specs import INSTALL_SPECS  # noqa: E402

INSTALL_OUTPUT_DIR = VOICE_ENGINE_DIR / "output" / "installs"


def _spec_lookup(model_id: str) -> ModelSpec | None:
    cls = ADAPTER_CLASSES.get(model_id)
    return cls.SPEC if cls is not None else None


def main(argv: list[str] | None = None) -> int:
    return run_install_cli(
        INSTALL_SPECS, _spec_lookup, INSTALL_OUTPUT_DIR,
        description="Voice model installer", argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
