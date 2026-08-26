"""Unit tests for llm_config. No live provider calls."""
from unittest.mock import MagicMock, patch

from sdoh_core import llm_config


def test_llm_model_defaults_to_sonnet_5_for_anthropic(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert llm_config.llm_model("anthropic") == "claude-sonnet-5"


def test_build_chat_model_anthropic_sonnet_5_omits_temperature():
    mock_cls = MagicMock(name="ChatAnthropic")
    mock_cls.return_value = MagicMock(name="llm")
    with patch.dict("sys.modules", {"langchain_anthropic": MagicMock(ChatAnthropic=mock_cls)}):
        llm_config.build_chat_model(
            provider="anthropic",
            model_name="claude-sonnet-5",
            temperature=0.0,
        )

    kwargs = mock_cls.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert "temperature" not in kwargs
    assert kwargs["max_tokens"] == 8192


def test_build_tool_calling_agent_uses_generic_agent_for_non_openai():
    llm = MagicMock(name="claude")
    with patch("sdoh_core.llm_config.ToolCallingAgent") as mock_generic, patch(
        "sdoh_core.llm_config.OpenAIToolCallingAgent"
    ):
        mock_generic.return_value = MagicMock(name="generic_agent")
        agent = llm_config.build_tool_calling_agent(llm, tools=[], force_tool=False)

    mock_generic.assert_called_once()
    assert agent is mock_generic.return_value


def test_llm_content_to_text_joins_anthropic_text_blocks():
    content = [
        {"type": "thinking", "thinking": "scratch"},
        {"type": "text", "text": "### Alpha\nDiabetes."},
        {"type": "text", "text": "### Scope\nRural Indiana."},
    ]

    text = llm_config.llm_content_to_text(content)

    assert "Alpha" in text
    assert "Rural Indiana" in text
    assert "scratch" not in text


def test_llm_content_to_text_passes_through_string():
    assert llm_config.llm_content_to_text("hello") == "hello"
