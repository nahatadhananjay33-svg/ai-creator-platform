"""Ensure Kokoro's English G2P dependency is present (Phase A3.10).

Kokoro's English pipeline (``misaki``) uses spaCy's ``en_core_web_sm`` model,
which is not a pip dependency of anything — so English synthesis fails with
spaCy ``[E050] Can't find model 'en_core_web_sm'`` unless it is fetched
explicitly. The installer fetches it at install time; this module lets callers
*verify* it before generating audio and self-heal if it is somehow absent
(e.g. a venv created before this fix). Never requires manual installation.

Stdlib-only at import time; spaCy is imported lazily, so this module is safe to
import anywhere (including outside the kokoro venv).
"""
from __future__ import annotations

import importlib.util

#: The spaCy model Kokoro's English G2P requires.
EN_G2P_MODEL = "en_core_web_sm"


def is_model_installed(model: str = EN_G2P_MODEL) -> bool:
    """True if the spaCy model package is importable in this interpreter."""
    return importlib.util.find_spec(model) is not None


def ensure_en_core_web_sm(model: str = EN_G2P_MODEL) -> bool:
    """Guarantee the English G2P model is available; download it if missing.

    Returns True if the model was already present, False if it had to be
    downloaded. Raises a clear ``RuntimeError`` if it cannot be made available.
    Idempotent and safe to call repeatedly.
    """
    if is_model_installed(model):
        return True
    if importlib.util.find_spec("spacy") is None:
        raise RuntimeError(
            "spaCy is not installed in this environment, so Kokoro's English G2P "
            "model cannot be fetched. Install Kokoro first: "
            "python -m voice_engine.scripts.install_models --models kokoro"
        )
    # uv-created venvs ship no pip; bootstrap it so spaCy's downloader works.
    if importlib.util.find_spec("pip") is None:
        import ensurepip

        ensurepip.bootstrap()
    from spacy.cli import download  # type: ignore[import-not-found]

    download(model)  # version-matched to the installed spaCy
    if not is_model_installed(model):
        raise RuntimeError(
            f"Failed to install spaCy model {model!r} for Kokoro English G2P."
        )
    return False
