"""Audit runner. Product injects the system prompt text."""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from sdoh_core.llm_config import (
    build_chat_model,
    llm_content_to_text,
    llm_model,
    llm_provider,
    model_display_name,
)


class AuditAgent:
    """Second-model review of a conversation turn. Prompt is product-owned."""

    def __init__(
        self,
        system_prompt: str,
        *,
        model_name: str | None = None,
        provider: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.system_prompt = system_prompt
        self.provider = provider or llm_provider()
        self.model_name = model_name or llm_model(self.provider)
        self.llm = build_chat_model(
            provider=self.provider,
            model_name=self.model_name,
            temperature=temperature,
        )

    def audit(self, user_prompt: str, conversation: str, final_answer: str) -> str:
        audit_context = f"""**USER REQUEST:**
{user_prompt}

**CONVERSATION CONTEXT:**
{conversation or "(none)"}

**FINAL ANSWER:**
{final_answer}
"""
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(
                content=(
                    "Please audit the following assistant interaction:\n\n"
                    f"{audit_context}"
                )
            ),
        ]
        response = self.llm.invoke(messages)
        return llm_content_to_text(response.content)

    def display_name(self) -> str:
        return model_display_name(self.llm)
