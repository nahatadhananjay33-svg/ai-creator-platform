"""Regression tests for the Kokoro weight manifest + verifier (Phase B2.1).

Hermetic: no network, no HF cache, no kokoro install. The verifier is exercised
through an injected resolver so presence/size logic is tested deterministically.
"""
from __future__ import annotations

from pathlib import Path

from voice_engine.models import kokoro_weights as kw


def test_manifest_matches_upstream_layout():
    names = {w.hf_filename for w in kw.KOKORO_WEIGHTS}
    # The two files Kokoro always loads + the two adapter-default voice packs.
    assert {"kokoro-v1_0.pth", "config.json",
            "voices/af_heart.pt", "voices/hf_alpha.pt"} <= names
    required = {w.hf_filename for w in kw.required_weight_files()}
    assert required == {"kokoro-v1_0.pth", "config.json",
                        "voices/af_heart.pt", "voices/hf_alpha.pt"}


def _resolver(present: dict[str, int]):
    """Build a resolver that maps hf_filename -> a real temp file of N bytes."""
    def resolve(hf_filename: str) -> Path | None:
        return present.get(hf_filename)
    return resolve


def _write(tmp_path: Path, name: str, nbytes: int) -> Path:
    p = tmp_path / name.replace("/", "_")
    p.write_bytes(b"\0" * nbytes)
    return p


def test_all_missing_when_cache_empty():
    statuses = kw.check_weights(resolver=lambda _f: None)
    assert all(s.status == "missing" for s in statuses)
    assert kw.all_required_valid(statuses) is False


def test_required_valid_when_all_present(tmp_path):
    present = {w.hf_filename: _write(tmp_path, w.hf_filename, w.min_bytes + 10)
               for w in kw.KOKORO_WEIGHTS}
    statuses = kw.check_weights(resolver=_resolver(present))
    assert all(s.status == "validated" for s in statuses)
    assert kw.all_required_valid(statuses) is True


def test_corrupted_when_under_size_floor(tmp_path):
    # Model file present but truncated below its floor -> corrupted, not valid.
    present = {"kokoro-v1_0.pth": _write(tmp_path, "kokoro-v1_0.pth", 10)}
    model = next(w for w in kw.KOKORO_WEIGHTS if w.hf_filename == "kokoro-v1_0.pth")
    s = kw.check_weight(model, resolver=_resolver(present))
    assert s.status == "corrupted"
    assert s.ok is False


def test_prefetch_code_is_valid_and_covers_every_file():
    code = kw.build_prefetch_code()
    assert "hf_hub_download" in code
    assert kw.KOKORO_REPO_ID in code
    for w in kw.KOKORO_WEIGHTS:
        assert w.hf_filename in code
    # Hard validation: a truncated download must assert, never pass silently.
    assert "assert sz >= s['min_bytes']" in code
    compile(code, "<prefetch>", "exec")  # must be valid Python
