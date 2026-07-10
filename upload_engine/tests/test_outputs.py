"""Output-writer tests (Phase C18) — metadata.json + upload_preview.md, hermetic."""
from __future__ import annotations

import json

from upload_engine.assistant import (
    METADATA_FILENAME,
    PREVIEW_FILENAME,
    generate_metadata,
    render_metadata_json,
    render_preview,
    write_upload_assets,
)


def test_write_creates_both_files(summary, tmp_path):
    md = generate_metadata(summary)
    files = write_upload_assets(md, tmp_path)
    assert files.metadata_json.name == METADATA_FILENAME
    assert files.preview_md.name == PREVIEW_FILENAME
    assert files.metadata_json.exists() and files.preview_md.exists()


def test_write_creates_missing_dir(summary, tmp_path):
    md = generate_metadata(summary)
    target = tmp_path / "nested" / "out"
    files = write_upload_assets(md, target)
    assert files.metadata_json.exists()


def test_metadata_json_roundtrips_all_fields(summary, tmp_path):
    md = generate_metadata(summary)
    files = write_upload_assets(md, tmp_path)
    data = json.loads(files.metadata_json.read_text(encoding="utf-8"))
    assert data == md.to_dict()
    # every required output serialised and non-empty
    for key in ("youtube_title", "youtube_description", "instagram_caption",
                "facebook_caption", "linkedin_post", "thumbnail_text",
                "suggested_filename"):
        assert data[key]
    assert data["hashtags"] and isinstance(data["hashtags"], list)


def test_preview_contains_every_output(summary):
    md = generate_metadata(summary)
    preview = render_preview(md)
    assert preview.startswith("# Upload Preview")
    for heading in ("YouTube — Title", "YouTube — Description", "Instagram",
                    "Facebook", "LinkedIn", "Hashtags", "Thumbnail Text",
                    "Suggested Filename"):
        assert heading in preview
    # the actual values appear in the sheet
    assert md.youtube_title in preview
    assert md.suggested_filename in preview
    assert " ".join(md.hashtags) in preview


def test_preview_blocks_are_copy_paste_fenced(summary):
    preview = render_preview(generate_metadata(summary))
    assert preview.count("```") >= 8 * 2 - 2   # a fence pair per section


def test_outputs_are_deterministic(summary, tmp_path):
    md = generate_metadata(summary)
    a = render_metadata_json(md), render_preview(md)
    b = render_metadata_json(md), render_preview(md)
    assert a == b


def test_written_files_are_byte_identical_across_runs(summary, tmp_path):
    md = generate_metadata(summary)
    f1 = write_upload_assets(md, tmp_path / "a")
    f2 = write_upload_assets(md, tmp_path / "b")
    assert f1.metadata_json.read_bytes() == f2.metadata_json.read_bytes()
    assert f1.preview_md.read_bytes() == f2.preview_md.read_bytes()


def test_preview_handles_backticks_in_content():
    from upload_engine.assistant import ReelSummary
    md = generate_metadata(ReelSummary(title="Code ``` fences", prompt="x"))
    preview = render_preview(md)
    # the fence used must be longer than any backtick run in the content
    assert "Code ``` fences" in preview
