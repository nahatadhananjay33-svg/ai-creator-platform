"""Regression tests for the Chatterbox weight manifest + verifier (Phase B2.2).

Hermetic: no network, no HF cache, no chatterbox install. The verifier is
exercised through an injected resolver so presence/size logic is tested
deterministically.
"""
from __future__ import annotations

from pathlib import Path

from voice_engine.models import chatterbox_weights as cw


def test_manifest_matches_from_pretrained_allow_patterns():
    # Exactly the ``allow_patterns`` set ChatterboxMultilingualTTS.from_pretrained
    # downloads for the default v2 model (verified against upstream mtl_tts.py).
    names = {w.hf_filename for w in cw.CHATTERBOX_WEIGHTS}
    assert names == {
        "t3_mtl23ls_v2.safetensors", "s3gen.pt", "ve.pt", "conds.pt",
        "grapheme_mtl_merged_expanded_v1.json", "Cangjie5_TC.json",
    }
    # The default T3 model is tracked as the big required backbone.
    assert cw.DEFAULT_T3_MODEL == "t3_mtl23ls_v2.safetensors"
    assert cw.DEFAULT_T3_MODEL in names
    # Every manifest file is required (from_pretrained fetches all of them).
    assert {w.hf_filename for w in cw.required_weight_files()} == names


def _resolver(present: dict[str, Path]):
    def resolve(hf_filename: str) -> Path | None:
        return present.get(hf_filename)
    return resolve


def _write(tmp_path: Path, name: str, nbytes: int) -> Path:
    p = tmp_path / name.replace("/", "_")
    p.write_bytes(b"\0" * nbytes)
    return p


def test_all_missing_when_cache_empty():
    statuses = cw.check_weights(resolver=lambda _f: None)
    assert all(s.status == "missing" for s in statuses)
    assert cw.all_required_valid(statuses) is False


def test_required_valid_when_all_present(tmp_path):
    present = {w.hf_filename: _write(tmp_path, w.hf_filename, w.min_bytes + 10)
               for w in cw.CHATTERBOX_WEIGHTS}
    statuses = cw.check_weights(resolver=_resolver(present))
    assert all(s.status == "validated" for s in statuses)
    assert cw.all_required_valid(statuses) is True


def test_corrupted_when_under_size_floor(tmp_path):
    # T3 backbone present but truncated below its floor -> corrupted, not valid.
    present = {"t3_mtl23ls_v2.safetensors": _write(tmp_path, "t3.safetensors", 10)}
    model = next(w for w in cw.CHATTERBOX_WEIGHTS
                 if w.hf_filename == "t3_mtl23ls_v2.safetensors")
    s = cw.check_weight(model, resolver=_resolver(present))
    assert s.status == "corrupted"
    assert s.ok is False
    # One corrupted required file fails the whole gate.
    statuses = cw.check_weights(resolver=_resolver(present))
    assert cw.all_required_valid(statuses) is False


def test_prefetch_code_is_valid_and_covers_every_file():
    code = cw.build_prefetch_code()
    assert "hf_hub_download" in code
    assert cw.CHATTERBOX_REPO_ID in code
    for w in cw.CHATTERBOX_WEIGHTS:
        assert w.hf_filename in code
    # Hard validation: a truncated download must assert, never pass silently.
    assert "assert sz >= s['min_bytes']" in code
    # No pip/ensurepip in the prefetch (pip-less-venv lesson).
    assert "ensurepip" not in code and "pip install" not in code
    compile(code, "<prefetch>", "exec")  # must be valid Python
