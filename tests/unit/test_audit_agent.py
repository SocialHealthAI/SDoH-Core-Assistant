"""Unit tests for AuditAgent. Mock LLM; product supplies the prompt."""
from unittest.mock import MagicMock, patch

from sdoh_core.audit_agent import AuditAgent


def test_constructor_uses_injected_prompt_not_product_outline():
    with patch("sdoh_core.audit_agent.build_chat_model") as mock_llm_fn:
        mock_llm_fn.return_value = MagicMock(name="llm")
        agent = AuditAgent(system_prompt="Audit this turn for gaps.")

    assert agent.system_prompt == "Audit this turn for gaps."
    assert "Problem Definition" not in agent.system_prompt
    assert "Problem Summary" not in agent.system_prompt


def test_audit_flattens_list_shaped_response():
    with patch("sdoh_core.audit_agent.build_chat_model") as mock_llm_fn:
        llm = MagicMock(name="llm")
        llm.invoke.return_value = MagicMock(
            content=[
                {"type": "thinking", "thinking": "scratch"},
                {"type": "text", "text": "**Issues Found**: None identified"},
            ]
        )
        mock_llm_fn.return_value = llm
        agent = AuditAgent(system_prompt="Be brief.")

    report = agent.audit("Draft a section.", "USER: hi", "Here is a draft.")

    assert "None identified" in report
    assert "scratch" not in report
    llm.invoke.assert_called_once()
