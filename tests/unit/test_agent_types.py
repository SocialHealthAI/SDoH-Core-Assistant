"""Unit tests for agent_types.ToolCallingAgent. No provider API."""
from unittest.mock import MagicMock

from sdoh_core.agent_types import ToolCallingAgent


def test_tool_calling_agent_with_no_tools_returns_output_and_empty_steps():
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Draft section")
    agent = ToolCallingAgent(
        tools=[],
        llm=llm,
        force_tool=False,
        system_prompt="You are an assistant.",
    )

    result = agent.run("Help me write the section.")

    assert result["output"] == "Draft section"
    assert result["intermediate_steps"] == []
    llm.invoke.assert_called_once()
