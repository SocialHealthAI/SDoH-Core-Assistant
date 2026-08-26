"""Unit tests for DocumentSectionTool. tmp_path only; no LLM."""
from pathlib import Path

import pytest

from sdoh_core.document_section_tool import DocumentSectionTool
from sdoh_core.requirements_file import RequirementsFileHelper

FIXTURE = (
    "# AI Solution Requirements Definition\n\n"
    "## 1. Alpha\n\n"
    "Original alpha body.\n\n"
    "## 3. Gamma\n\n"
    "Keep gamma.\n"
)


def test_propose_section_does_not_write(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    tool = DocumentSectionTool(helper, heading="1. Alpha")

    proposed = tool.propose_section("doc.md", "### Summary\nNew")

    assert proposed["wrote"] is False
    assert proposed["type"] == "proposed_write"
    assert proposed["heading"] == "1. Alpha"
    assert not helper.exists("doc.md")
    assert "New" in proposed["proposed_full_text"]
    assert proposed["review_markdown"].startswith("## 1. Alpha")


def test_review_observation_includes_proposed_section():
    helper = RequirementsFileHelper()
    tool = DocumentSectionTool(helper, heading="2. Beta")
    proposed = {
        "path": "demo.md",
        "summary": "Create the file.",
        "heading": "2. Beta",
        "review_markdown": "## 2. Beta\n\n### Summary\nOutline.\n",
        "proposed_full_text": "# Title\n",
    }

    observation = tool.review_observation(proposed)

    assert "not saved" in observation.lower() or "Confirm write" in observation
    assert "### Summary" in observation
    assert "Outline." in observation
    assert "## 2. Beta" in observation


def test_apply_proposed_write_without_confirm_does_not_write(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    tool = DocumentSectionTool(helper, heading="1. Alpha")
    proposed = tool.propose_section("doc.md", "body")

    with pytest.raises(PermissionError):
        tool.apply_proposed_write(proposed, confirm=False)

    assert not helper.exists("doc.md")


def test_apply_proposed_write_with_confirm_creates_file(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    tool = DocumentSectionTool(helper, heading="1. Alpha")
    proposed = tool.propose_section("doc.md", "### Summary\nSaved")

    tool.apply_proposed_write(proposed, confirm=True)

    text = helper.read("doc.md")
    assert "## 1. Alpha" in text
    assert "Saved" in text
    assert "# AI Solution Requirements Definition" in text


def test_propose_preserves_other_sections(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    helper.write("doc.md", FIXTURE, confirm=True)
    tool = DocumentSectionTool(helper, heading="1. Alpha")

    proposed = tool.propose_section("doc.md", "Updated alpha only")
    tool.apply_proposed_write(proposed, confirm=True)

    text = helper.read("doc.md")
    assert "Updated alpha only" in text
    assert "## 3. Gamma" in text
    assert "Keep gamma." in text
    assert "Original alpha body." not in text


def test_inserts_missing_numbered_section_in_numeric_order(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    helper.write("doc.md", FIXTURE, confirm=True)
    tool = DocumentSectionTool(helper, heading="2. Beta")

    proposed = tool.propose_section("doc.md", "Inserted beta")
    tool.apply_proposed_write(proposed, confirm=True)

    text = helper.read("doc.md")
    alpha = text.index("## 1. Alpha")
    beta = text.index("## 2. Beta")
    gamma = text.index("## 3. Gamma")
    assert alpha < beta < gamma
    assert "Inserted beta" in text
    assert "Keep gamma." in text


def test_current_section_reads_bound_heading(tmp_path: Path):
    helper = RequirementsFileHelper(tmp_path)
    helper.write("doc.md", FIXTURE, confirm=True)
    tool = DocumentSectionTool(helper, heading="1. Alpha")

    body = tool.current_section("doc.md")

    assert body is not None
    assert "Original alpha body." in body
    assert "Keep gamma." not in body
