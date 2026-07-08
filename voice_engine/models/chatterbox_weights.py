"""Chatterbox pretrained-weight manifest, verification, and prefetch (Phase B2.2).

Single source of truth for the files Chatterbox Multilingual needs, taken from
upstream — ``ChatterboxMultilingualTTS.from_pretrained`` (resemble-ai/chatterbox)
does a ``snapshot_download(repo_id="ResembleAI/chatterbox",
allow_patterns=[...])``, so this manifest lists *exactly* that ``allow_patterns``
set for the default multilingual model (``t3_mtl23ls_v2.safetensors``). Not
guessed. Mirrors the Kokoro / Avatar-Engine weight-manifest modules
(``kokoro_weights.py`` / ``musetalk_weights.py`` / ``latentsync_weights.py``):
the module owns the **manifest**, a presence/size **verifier**, and a
**prefetch** snippet.

Like Kokoro (and unlike the Avatar models, which clone a repo and place weights
under ``<repo>/checkpoints/``), Chatterbox is a pip package that pulls its
weights from the HF Hub into the shared HF cache on first use. So the manifest
lists HF repo files and the verifier resolves them against the **HF cache**
(``huggingface_hub.try_to_load_from_cache``) rather than a checkpoints directory.

``from_pretrained`` downloads exactly (default v2 model):

    t3_mtl23ls_v2.safetensors            — 23-language T3 backbone (~2.0 GB)
    s3gen.pt                             — S3 codec generator/decoder (~1.0 GB)
    ve.pt                                — voice encoder (~5.4 MB)
    conds.pt                             — built-in default voice conditionals
    grapheme_mtl_merged_expanded_v1.json — multilingual grapheme tokenizer
    Cangjie5_TC.json                     — Chinese (Cangjie) tokenizer table

Exact SHA256 is not published upstream, so verification checks presence + a
non-trivial-size floor (catches truncated / HTML-error downloads).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

#: HF repo Chatterbox pulls its weights from (matches ``mtl_tts.REPO_ID``).
CHATTERBOX_REPO_ID = "ResembleAI/chatterbox"

#: Default multilingual T3 checkpoint (``mtl_tts.DEFAULT_MULTILINGUAL_T3_MODEL``).
#: The adapter uses the default, so the manifest tracks the v2 model.
DEFAULT_T3_MODEL = "t3_mtl23ls_v2.safetensors"


@dataclass(frozen=True)
class WeightFile:
    """One Chatterbox weight file within the HF repo.

    ``min_bytes`` is a per-file size floor — a real file must be at least this
    big, which catches truncated / HTML-error downloads without needing exact
    sizes (not published upstream).
    """

    hf_filename: str
    purpose: str
    required: bool
    min_bytes: int


#: The full ``from_pretrained`` ``allow_patterns`` set for the default v2 model.
#: All are required: ``from_pretrained`` fetches every one, and ``from_local``
#: loads the T3 backbone, S3 codec, voice encoder, tokenizers, and the built-in
#: voice conditionals. Floors are ~half the real upstream size — enough to catch
#: a truncated download, loose enough to survive a minor upstream re-export.
CHATTERBOX_WEIGHTS: tuple[WeightFile, ...] = (
    WeightFile(DEFAULT_T3_MODEL, "23-language T3 backbone (0.5B)", True, 2_000_000_000),
    WeightFile("s3gen.pt", "S3 codec generator/decoder", True, 900_000_000),
    WeightFile("ve.pt", "voice encoder", True, 4_000_000),
    WeightFile("conds.pt", "built-in default voice conditionals", True, 50_000),
    WeightFile("grapheme_mtl_merged_expanded_v1.json", "multilingual grapheme tokenizer",
               True, 40_000),
    WeightFile("Cangjie5_TC.json", "Chinese (Cangjie) tokenizer table", True, 1_000_000),
)


def required_weight_files() -> list[WeightFile]:
    return [w for w in CHATTERBOX_WEIGHTS if w.required]


def default_resolver(hf_filename: str, repo_id: str = CHATTERBOX_REPO_ID) -> Path | None:
    """Local cached path for an HF repo file, or ``None`` if not in the HF cache.

    Uses ``try_to_load_from_cache`` so verification stays **offline** — it never
    hits the network, it only inspects what has already been downloaded. This
    resolves the same cache ``snapshot_download`` populates, so a prefetched
    install verifies without a network round-trip.
    """
    from huggingface_hub import try_to_load_from_cache  # type: ignore[import-not-found]

    hit = try_to_load_from_cache(repo_id, hf_filename)
    return Path(hit) if isinstance(hit, str) else None


@dataclass
class WeightStatus:
    relpath: str
    purpose: str
    required: bool
    actual_bytes: int | None
    status: str   # "validated" | "missing" | "corrupted"
    reason: str

    @property
    def ok(self) -> bool:
        return self.status == "validated"

    def to_dict(self) -> dict:
        return {
            "relpath": self.relpath, "purpose": self.purpose, "required": self.required,
            "actual_bytes": self.actual_bytes, "status": self.status,
            "reason": self.reason, "ok": self.ok,
        }


def check_weight(w: WeightFile, resolver: Callable[[str], Path | None] = default_resolver) -> WeightStatus:
    path = resolver(w.hf_filename)
    if path is None or not path.exists():
        return WeightStatus(w.hf_filename, w.purpose, w.required, None,
                            "missing", "not in HF cache")
    actual = path.stat().st_size
    if actual < w.min_bytes:
        return WeightStatus(w.hf_filename, w.purpose, w.required, actual, "corrupted",
                            f"{actual} bytes < {w.min_bytes} floor (truncated/incomplete)")
    return WeightStatus(w.hf_filename, w.purpose, w.required, actual, "validated",
                        "present and non-trivial size")


def check_weights(resolver: Callable[[str], Path | None] = default_resolver) -> list[WeightStatus]:
    return [check_weight(w, resolver) for w in CHATTERBOX_WEIGHTS]


def all_required_valid(statuses: list[WeightStatus]) -> bool:
    req = [s for s in statuses if s.required]
    return bool(req) and all(s.ok for s in req)


def build_prefetch_code() -> str:
    """Self-contained snippet (run inside the Chatterbox venv) that downloads
    every manifest file straight from this module — idempotent
    (``hf_hub_download`` skips already-cached files) and hard-validated (raises
    if any file is missing or under its size floor, so a partial download can
    never be reported as success). Pre-populates the exact HF-cache snapshot
    ``from_pretrained`` expects, making a fresh install offline-ready rather than
    relying on Chatterbox's lazy first-use ``snapshot_download``. huggingface_hub
    only; no pip/ensurepip (the LatentSync/Kokoro pip-less-venv lesson).
    """
    specs = [{"hf_filename": w.hf_filename, "min_bytes": w.min_bytes}
             for w in CHATTERBOX_WEIGHTS]
    return (
        "import os\n"
        "from huggingface_hub import hf_hub_download\n"
        f"repo_id = {CHATTERBOX_REPO_ID!r}\n"
        f"specs = {specs!r}\n"
        "for s in specs:\n"
        "    p = hf_hub_download(repo_id=repo_id, filename=s['hf_filename'])\n"
        "    sz = os.path.getsize(p)\n"
        "    assert sz >= s['min_bytes'], (s['hf_filename'], sz)\n"
        "    print('chatterbox weight ready:', s['hf_filename'], sz)\n"
        "print('chatterbox weights prefetch complete')\n"
    )
