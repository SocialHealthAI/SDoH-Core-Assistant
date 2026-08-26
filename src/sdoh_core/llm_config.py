"""
LLM provider selection for SDoH assistants.

OpenAI is the default. Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY
to run Claude (including Claude Sonnet 5).
"""
from __future__ import annotations

import os
from typing import Any

from sdoh_core.agent_types import OpenAIToolCallingAgent, ToolCallingAgent

PROVIDER_OPENAI = "openai"
PROVIDER_ANTHROPIC = "anthropic"

DEFAULT_MODELS = {
    PROVIDER_OPENAI: "gpt-5.2",
    PROVIDER_ANTHROPIC: "claude-sonnet-5",
}

_SONNET_5_PREFIX = "claude-sonnet-5"


def llm_provider() -> str:
    raw = (os.environ.get("LLM_PROVIDER") or PROVIDER_OPENAI).strip().lower()
    if raw in ("claude", "anthropic"):
        return PROVIDER_ANTHROPIC
    if raw in ("openai",):
        return PROVIDER_OPENAI
    raise ValueError(
        f"Unsupported LLM_PROVIDER={raw!r}. Use 'openai' or 'anthropic'."
    )


def llm_model(provider: str | None = None) -> str:
    env = (os.environ.get("LLM_MODEL") or "").strip()
    if env:
        return env
    return DEFAULT_MODELS[provider or llm_provider()]


def _is_sonnet_5(model_name: str) -> bool:
    return model_name.lower().startswith(_SONNET_5_PREFIX)


def build_chat_model(
    *,
    provider: str | None = None,
    model_name: str | None = None,
    temperature: float = 0.0,
) -> Any:
    chosen_provider = (provider or llm_provider()).strip().lower()
    if chosen_provider in ("claude",):
        chosen_provider = PROVIDER_ANTHROPIC
    model = model_name or llm_model(chosen_provider)

    if chosen_provider == PROVIDER_ANTHROPIC:
        from langchain_anthropic import ChatAnthropic

        kwargs: dict[str, Any] = {"model": model, "max_tokens": 8192}
        if not _is_sonnet_5(model):
            kwargs["temperature"] = temperature
        return ChatAnthropic(**kwargs)

    if chosen_provider == PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, temperature=temperature)

    raise ValueError(
        f"Unsupported LLM_PROVIDER={chosen_provider!r}. Use 'openai' or 'anthropic'."
    )


def build_tool_calling_agent(llm: Any, tools: list[Any], **kwargs: Any) -> Any:
    """OpenAI keeps the typed wrapper; Anthropic uses generic tool-calling."""
    try:
        from langchain_openai import ChatOpenAI
    except Exception:
        ChatOpenAI = None  # type: ignore
    if ChatOpenAI is not None and isinstance(llm, ChatOpenAI):
        return OpenAIToolCallingAgent(tools=tools, llm=llm, **kwargs)
    return ToolCallingAgent(tools=tools, llm=llm, **kwargs)


def model_display_name(llm: Any) -> str:
    return (
        getattr(llm, "model", None)
        or getattr(llm, "model_name", None)
        or type(llm).__name__
    )


def llm_content_to_text(content: Any) -> str:
    """Flatten provider message content (including Anthropic block lists) to a string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            text = _block_to_text(block)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return str(content)


def _block_to_text(block: Any) -> str:
    if block is None:
        return ""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        block_type = str(block.get("type") or "")
        if block_type in ("thinking", "tool_use", "tool_result"):
            return ""
        text = block.get("text")
        if isinstance(text, str):
            return text
        return ""
    block_type = str(getattr(block, "type", "") or "")
    if block_type in ("thinking", "tool_use", "tool_result"):
        return ""
    text = getattr(block, "text", None)
    if isinstance(text, str):
        return text
    inner = getattr(block, "content", None)
    if inner is not None and inner is not block:
        return llm_content_to_text(inner)
    return ""
