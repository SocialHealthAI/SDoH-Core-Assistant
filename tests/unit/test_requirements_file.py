"""Unit tests for RequirementsFileHelper. No LLM. Uses tmp_path."""
from pathlib import Path

import pytest

from sdoh_core.requirements_file import MarkdownSection, RequirementsFileHelper


def test_resolve_relative_path_stays_under_root(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    resolved = helper.resolve("ai-solution-requirements-definition.md")

    assert resolved == (tmp_path / "ai-solution-requirements-definition.md").resolve()


def test_resolve_documents_prefix_maps_onto_root(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    resolved = helper.resolve("documents/nested/file.md")

    assert resolved == (tmp_path / "nested" / "file.md").resolve()


def test_resolve_sdoh_documents_prefix_maps_onto_root(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    resolved = helper.resolve("sdoh_documents/nested/file.md")

    assert resolved == (tmp_path / "nested" / "file.md").resolve()


def test_resolve_parent_escape_raises(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    with pytest.raises(ValueError, match="outside"):
        helper.resolve("../secret.md")


def test_resolve_null_byte_raises(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    with pytest.raises(ValueError, match="Invalid path"):
        helper.resolve("foo\x00.md")


def test_resolve_absolute_outside_root_raises(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    outside = tmp_path.resolve().parent / "not-in-sandbox.md"

    with pytest.raises(ValueError, match="outside"):
        helper.resolve(str(outside))


def test_write_without_confirm_raises_and_does_not_create_file(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    with pytest.raises(PermissionError, match="confirm"):
        helper.write("draft.md", "# no\n", confirm=False)

    assert not (tmp_path / "draft.md").exists()


def test_write_with_confirm_creates_file(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    helper.write("draft.md", "# yes\n", confirm=True)

    assert (tmp_path / "draft.md").read_text(encoding="utf-8") == "# yes\n"


def test_parse_and_render_round_trip_preserves_sibling_sections(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    original = (
        "# AI Solution Requirements Definition\n\n"
        "## 1. Alpha\n\n"
        "Old body\n\n"
        "## 2. Beta\n\n"
        "Keep me\n"
    )

    preamble, sections = helper.parse(original)
    rendered = helper.render(preamble, sections)

    assert "## 2. Beta" in rendered
    assert "Keep me" in rendered
    assert helper.parse(rendered)[1][1].heading == "2. Beta"


def test_exists_and_last_saved(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    helper.write("a.md", "x\n", confirm=True)

    assert helper.exists("a.md") is True
    assert helper.exists("missing.md") is False
    assert helper.last_saved("a.md") is not None
    assert helper.last_saved("missing.md") is None
    missing = helper.fingerprint("missing.md")
    assert missing["exists"] is False
    assert missing["sha256"] is None
    present = helper.fingerprint("a.md")
    assert present["exists"] is True
    assert present["sha256"] == helper.fingerprint("a.md")["sha256"]


def test_parse_empty_text_returns_no_sections(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)

    preamble, sections = helper.parse("")

    assert preamble == ""
    assert sections == []
    assert isinstance(MarkdownSection("h", "b"), MarkdownSection)
