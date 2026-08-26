"""Unit tests for Core ReActAgent. Mock LLM/executor; no network."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from sdoh_core.document_section_tool import DocumentSectionTool
from sdoh_core.react_agent import ReActAgent
from sdoh_core.requirements_file import RequirementsFileHelper


def _make_agent(tmp_path: Path, prompt_path: Path, tools=None, document_tool=None):
    with patch("sdoh_core.react_agent.build_chat_model") as mock_llm_fn, patch(
        "sdoh_core.react_agent.build_tool_calling_agent"
    ) as mock_agent_fn:
        mock_llm_fn.return_value = MagicMock(name="llm")
        inner = MagicMock(name="tool_calling_agent")
        mock_agent_fn.return_value = inner
        agent = ReActAgent(
            tools=tools or [],
            system_prompt_path=str(prompt_path),
            documents_root=tmp_path,
            document_tool=document_tool,
        )
        agent._mock_tool_calling_agent = inner
        agent._mock_build_fn = mock_agent_fn
        return agent


def test_injected_mock_tool_is_passed_to_build_tool_calling_agent(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("You are a test assistant.", encoding="utf-8")
    mock_tool = MagicMock(name="injected_tool")
    mock_tool.name = "example_tool"

    agent = _make_agent(tmp_path, prompt, tools=[mock_tool])

    assert agent.tools == [mock_tool]
    tools_arg = agent._mock_build_fn.call_args.args[1]
    assert tools_arg == [mock_tool]


def test_load_system_prompt_returns_file_contents(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("You are a test assistant.", encoding="utf-8")

    agent = _make_agent(tmp_path, prompt)

    assert "test assistant" in agent.system_prompt


def test_load_system_prompt_missing_file_returns_empty_string(tmp_path: Path):
    missing = tmp_path / "does_not_exist.txt"

    agent = _make_agent(tmp_path, missing)

    assert agent.system_prompt == ""


def test_history_messages_skips_duplicate_current_user_prompt(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    agent = _make_agent(tmp_path, prompt)
    history = [
        {"role": "assistant", "content": "Hello."},
        {"role": "user", "content": "Add success measures."},
    ]

    messages = agent._history_messages(history, "Add success measures.")

    assert all(not (isinstance(m, HumanMessage) and m.content == "Add success measures.") for m in messages)
    assert any(isinstance(m, AIMessage) for m in messages)


def test_run_flattens_list_shaped_llm_output(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    agent = _make_agent(tmp_path, prompt)
    agent._mock_tool_calling_agent.run.return_value = {
        "output": [
            {"type": "thinking", "thinking": "plan"},
            {"type": "text", "text": "## 2. Beta"},
        ],
        "intermediate_steps": [],
    }

    result = agent.run("Add a section.")

    assert result["output"] == "## 2. Beta"


def test_run_extracts_pending_write_from_tool_observation(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    agent = _make_agent(tmp_path, prompt)
    payload = {
        "type": "proposed_write",
        "path": "documents/file.md",
        "heading": "2. Beta",
        "summary": "Create the file.",
        "proposed_full_text": "# AI Solution Requirements Definition\n",
        "wrote": False,
    }
    agent._mock_tool_calling_agent.run.return_value = {
        "output": "Click Confirm write in the sidebar.",
        "intermediate_steps": [
            ("example_tool", json.dumps(payload)),
        ],
    }

    result = agent.run("Please save the draft.")

    assert result["pending_write"]["summary"] == "Create the file."
    assert result["pending_write"]["wrote"] is False
    assert "# AI Solution Requirements Definition" in result["output"]
    assert "2. Beta" in result["output"]


def test_propose_section_does_not_write_until_apply(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    helper = RequirementsFileHelper(tmp_path)
    document_tool = DocumentSectionTool(helper, heading="1. Alpha")
    agent = _make_agent(tmp_path, prompt, document_tool=document_tool)

    proposed = agent.propose_document_update("doc.md", "### Summary\nHi")

    assert helper.exists("doc.md") is False
    agent.apply_pending_write(proposed)
    assert "Hi" in helper.read("doc.md")


def test_run_uses_tool_pending_and_puts_review_in_output(tmp_path: Path):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("prompt", encoding="utf-8")
    helper = RequirementsFileHelper(tmp_path)
    document_tool = DocumentSectionTool(helper, heading="1. Alpha")
    agent = _make_agent(tmp_path, prompt, document_tool=document_tool)
    agent._doc_path = "demo.md"

    def fake_run(_prompt, chat_history=None):
        observation = agent.propose_section_update("### Summary\nDiabetes in rural Indiana.\n")
        return {
            "output": "Please click Confirm write in the sidebar.",
            "intermediate_steps": [
                ("example_tool", observation),
            ],
        }

    agent._mock_tool_calling_agent.run.side_effect = fake_run

    result = agent.run("Save an outline to demo.md.")

    assert result["pending_write"]["path"] == "demo.md"
    assert "Diabetes in rural Indiana." in result["output"]
    assert "Please click Confirm write" in result["output"]
    assert not helper.exists("demo.md")
