"""The single command: pre-flight validation + the end-to-end happy path."""
from __future__ import annotations

import json
import dataclasses

import pytest

from creator.errors import CreatorError
from creator.run import _preflight, _run_id_for, main, run


# --------------------------------------------------------------------------- #
# Pre-flight validation (fast — no render)
# --------------------------------------------------------------------------- #
def test_preflight_accepts_a_valid_request(base_config):
    _preflight(base_config)                 # must not raise


def test_preflight_rejects_empty_prompt(base_config):
    cfg = dataclasses.replace(base_config, prompt="   ")
    with pytest.raises(CreatorError) as exc:
        _preflight(cfg)
    assert exc.value.hint                    # actionable hint present


def test_preflight_rejects_unknown_template(base_config):
    cfg = dataclasses.replace(base_config, template="not_a_template")
    with pytest.raises(CreatorError) as exc:
        _preflight(cfg)
    assert "not_a_template" in exc.value.message


def test_preflight_rejects_unknown_profile(base_config):
    cfg = dataclasses.replace(base_config, profiles=("reel_9x16", "bogus"))
    with pytest.raises(CreatorError):
        _preflight(cfg)


def test_preflight_rejects_empty_profiles(base_config):
    cfg = dataclasses.replace(base_config, profiles=())
    with pytest.raises(CreatorError):
        _preflight(cfg)


def test_run_id_is_a_deterministic_slug(base_config):
    rid = _run_id_for(base_config, None)
    assert rid == _run_id_for(base_config, None)
    assert rid == "a-quick-reel-about-saving-money"
    assert _run_id_for(base_config, "My Reel") == "my-reel"


# --------------------------------------------------------------------------- #
# End-to-end (hermetic mock renderer)
# --------------------------------------------------------------------------- #
def test_end_to_end_generates_upload_ready_reel(base_config):
    code = run(base_config, quiet=True)
    assert code == 0

    exports = (base_config_workspace(base_config) / "exports"
               / "a-quick-reel-about-saving-money")
    metadata_json = exports / "metadata.json"
    preview_md = exports / "upload_preview.md"
    assert metadata_json.is_file()
    assert preview_md.is_file()

    data = json.loads(metadata_json.read_text(encoding="utf-8"))
    assert data["youtube_title"]
    assert data["hashtags"]

    # the finished renditions are bundled next to the metadata
    renditions = list(exports.glob("*.avi")) + list(exports.glob("*.mp4"))
    assert renditions

    # the run itself lives under projects/
    assert (base_config_workspace(base_config) / "projects"
            / "a-quick-reel-about-saving-money").is_dir()


def test_cli_main_end_to_end(tmp_path):
    code = main([
        "--prompt", "Three ways to start investing",
        "--template", "finance",
        "--profiles", "reel_9x16",
        "--workspace", str(tmp_path / "ws"),
        "--quiet",
    ])
    assert code == 0
    out = tmp_path / "ws" / "exports" / "three-ways-to-start-investing"
    assert (out / "metadata.json").is_file()


def test_cli_main_reports_bad_config_without_raising(tmp_path, capsys):
    code = main(["--config", str(tmp_path / "does-not-exist.yaml")])
    assert code == 1
    err = capsys.readouterr().err
    assert "Error:" in err and "Hint:" in err


def base_config_workspace(cfg):
    from creator.paths import resolve_workspace
    return resolve_workspace(cfg.workspace_root).root
