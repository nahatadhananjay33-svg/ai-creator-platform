"""Kokoro pretrained-weight manifest, verification, and prefetch (Phase B2.1).

Single source of truth for the files Kokoro-82M needs, taken from upstream
(`hexgrad/Kokoro-82M` on Hugging Face) — not guessed. Mirrors the Avatar
Engine's weight-manifest modules (`musetalk_weights.py` / `latentsync_weights.py`):
the module owns the **manifest**, a presence/size **verifier**, and a
**prefetch** snippet.

Unlike the Avatar models (which clone a repo and place weights under
`<repo>/checkpoints/`), Kokoro is a pip package that pulls its weights from the
HF Hub into the shared HF cache on first use. So the manifest lists HF repo
files and the verifier resolves them against the **HF cache**
(`huggingface_hub.try_to_load_from_cache`) rather than a checkpoints directory.

Kokoro loads exactly:

    kokoro-v1_0.pth   — the 82M model (~327 MB)
    config.json       — model config
    voices/<name>.pt  — one voice-pack tensor per voice; the adapter defaults to
                        af_heart (English) and hf_alpha (Hindi).

Exact SHA256 is not published upstream, so verification checks presence + a
non-trivial-size floor (catches truncated / HTML-error downloads).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

#: HF repo Kokoro pulls its weights from (matches the adapter's ``repo_id``).
KOKORO_REPO_ID = "hexgrad/Kokoro-82M"


@dataclass(frozen=True)
class WeightFile:
    """One Kokoro weight file within the HF repo.

    ``min_bytes`` is a per-file size floor — a real file must be at least this
    big, which catches truncated / HTML-error downloads without needing exact
    sizes (not published upstream).
    """

    hf_filename: str
    purpose: str
    required: bool
    min_bytes: int


#: The full set Kokoro loads. Required = what the adapter needs for EN + HI
#: (its two production languages); the extra Hindi voice packs are optional.
KOKORO_WEIGHTS: tuple[WeightFile, ...] = (
    WeightFile("kokoro-v1_0.pth", "Kokoro 82M model weights", True, 100_000_000),
    WeightFile("config.json", "model config", True, 500),
    WeightFile("voices/af_heart.pt", "default English voice pack", True, 50_000),
    WeightFile("voices/hf_alpha.pt", "default Hindi voice pack", True, 50_000),
    WeightFile("voices/hf_beta.pt", "Hindi female voice pack", False, 50_000),
    WeightFile("voices/hm_omega.pt", "Hindi male voice pack", False, 50_000),
    WeightFile("voices/hm_psi.pt", "Hindi male voice pack", False, 50_000),
)


def required_weight_files() -> list[WeightFile]:
    return [w for w in KOKORO_WEIGHTS if w.required]


def default_resolver(hf_filename: str, repo_id: str = KOKORO_REPO_ID) -> Path | None:
    """Local cached path for an HF repo file, or ``None`` if not in the HF cache.

    Uses ``try_to_load_from_cache`` so verification stays **offline** — it never
    hits the network, it only inspects what has already been downloaded.
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
    return [check_weight(w, resolver) for w in KOKORO_WEIGHTS]


def all_required_valid(statuses: list[WeightStatus]) -> bool:
    req = [s for s in statuses if s.required]
    return bool(req) and all(s.ok for s in req)


def build_prefetch_code() -> str:
    """Self-contained snippet (run inside the Kokoro venv) that downloads every
    manifest file straight from this module — idempotent (``hf_hub_download``
    skips already-cached files) and hard-validated (raises if any file is
    missing or under its size floor, so a partial download can never be
    reported as success). Makes a fresh install offline-ready rather than
    relying on Kokoro's lazy first-use download.
    """
    specs = [{"hf_filename": w.hf_filename, "required": w.required, "min_bytes": w.min_bytes}
             for w in KOKORO_WEIGHTS]
    return (
        "import os\n"
        "from huggingface_hub import hf_hub_download\n"
        f"repo_id = {KOKORO_REPO_ID!r}\n"
        f"specs = {specs!r}\n"
        "for s in specs:\n"
        "    p = hf_hub_download(repo_id=repo_id, filename=s['hf_filename'])\n"
        "    sz = os.path.getsize(p)\n"
        "    assert sz >= s['min_bytes'], (s['hf_filename'], sz)\n"
        "    print('kokoro weight ready:', s['hf_filename'], sz)\n"
        "print('kokoro weights prefetch complete')\n"
    )
