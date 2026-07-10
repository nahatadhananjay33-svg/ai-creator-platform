"""Batch input parsing + validation across CSV / JSON / YAML."""
from __future__ import annotations

import json

import pytest
import yaml

from batch_runner.errors import BatchError
from batch_runner.input import load_entries


# --------------------------------------------------------------------------- #
# Happy paths per format
# --------------------------------------------------------------------------- #
def test_csv_basic(tmp_path):
    p = tmp_path / "reels.csv"
    p.write_text(
        "prompt,template,output\n"
        "Save money fast,finance,reel_one\n"
        "Buy your first home,real_estate,reel_two\n",
        encoding="utf-8",
    )
    entries = load_entries(p)
    assert [e.name for e in entries] == ["reel-one", "reel-two"]
    assert entries[0].prompt == "Save money fast"
    assert entries[0].template == "finance"


def test_csv_flat_overrides(tmp_path):
    p = tmp_path / "reels.csv"
    p.write_text(
        "prompt,template,renderer,profiles,quality_gate\n"
        "Hello world,general,mock,reel_9x16 square_1x1,false\n",
        encoding="utf-8",
    )
    (entry,) = load_entries(p)
    ov = entry.config_overrides()
    assert ov["generation"]["renderer"] == "mock"
    assert ov["generation"]["profiles"] == ["reel_9x16", "square_1x1"]
    assert ov["quality"]["gate"] is False


def test_json_list(tmp_path):
    p = tmp_path / "reels.json"
    p.write_text(json.dumps([
        {"prompt": "A", "template": "finance", "output": "a"},
        {"prompt": "B", "output": "b", "overrides": {"generation": {"language": "hi"}}},
    ]), encoding="utf-8")
    entries = load_entries(p)
    assert entries[1].config_overrides()["generation"]["language"] == "hi"


def test_yaml_reels_key(tmp_path):
    p = tmp_path / "reels.yaml"
    p.write_text(yaml.safe_dump({"reels": [
        {"prompt": "One", "template": "news"},
        {"prompt": "Two", "template": "news", "output": "second"},
    ]}), encoding="utf-8")
    entries = load_entries(p)
    assert entries[0].name == "one"           # defaults to prompt slug
    assert entries[1].name == "second"


def test_default_output_is_prompt_slug(tmp_path):
    p = tmp_path / "reels.json"
    p.write_text(json.dumps([{"prompt": "Why saving matters"}]), encoding="utf-8")
    (entry,) = load_entries(p)
    assert entry.name == "why-saving-matters"


# --------------------------------------------------------------------------- #
# Validation failures
# --------------------------------------------------------------------------- #
def test_missing_file(tmp_path):
    with pytest.raises(BatchError):
        load_entries(tmp_path / "nope.csv")


def test_unsupported_format(tmp_path):
    p = tmp_path / "reels.txt"
    p.write_text("prompt\n", encoding="utf-8")
    with pytest.raises(BatchError):
        load_entries(p)


def test_empty_batch(tmp_path):
    p = tmp_path / "reels.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(BatchError):
        load_entries(p)


def test_missing_prompt(tmp_path):
    p = tmp_path / "reels.csv"
    p.write_text("prompt,template\n,finance\n", encoding="utf-8")
    with pytest.raises(BatchError):
        load_entries(p)


def test_unknown_field_is_rejected(tmp_path):
    p = tmp_path / "reels.csv"
    p.write_text("prompt,rendrer\nHi,mock\n", encoding="utf-8")  # typo'd column
    with pytest.raises(BatchError) as exc:
        load_entries(p)
    assert "rendrer" in exc.value.message


def test_duplicate_output_rejected(tmp_path):
    p = tmp_path / "reels.json"
    p.write_text(json.dumps([
        {"prompt": "A", "output": "same"},
        {"prompt": "B", "output": "same"},
    ]), encoding="utf-8")
    with pytest.raises(BatchError) as exc:
        load_entries(p)
    assert "Duplicate" in exc.value.message


def test_duplicate_prompt_slug_rejected(tmp_path):
    p = tmp_path / "reels.json"
    p.write_text(json.dumps([{"prompt": "Same idea"}, {"prompt": "Same idea"}]),
                 encoding="utf-8")
    with pytest.raises(BatchError):
        load_entries(p)
