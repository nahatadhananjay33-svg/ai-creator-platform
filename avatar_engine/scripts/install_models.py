"""Install avatar models into isolated venvs and report results.

    python -m avatar_engine.scripts.install_models --report-only
    python -m avatar_engine.scripts.install_models --models sadtalker liveportrait

Thin wrapper over the shared foundation install CLI (same driver as the
voice engine). Reports land in avatar_engine/output/installs/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from foundation.model_manager.install_cli import run_install_cli  # noqa: E402
from foundation.model_manager.spec import ModelSpec  # noqa: E402
from avatar_engine.models.install_specs import INSTALL_SPECS  # noqa: E402

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "installs"


def _spec_lookup(model_id: str) -> ModelSpec | None:
    from avatar_engine.research.catalog import get_profile

    try:
        return get_profile(model_id).spec
    except Exception:  # noqa: BLE001 - models without research profiles
        return None


def main(argv: list[str] | None = None) -> int:
    return run_install_cli(
        INSTALL_SPECS, _spec_lookup, OUTPUT_DIR,
        description="Avatar model installer", argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())
