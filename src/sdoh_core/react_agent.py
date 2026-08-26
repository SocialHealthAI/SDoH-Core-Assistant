"""Conversation / Requirements Agent shell.

Products pass LangChain tools. Optional document_tool supplies file context
and confirm-before-write. No product heading names are hardcoded here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import AIMessage, HumanMessage

from sdoh_core.document_section_tool import PROPOSED_WRITE_TYPE, DocumentSectionTool
from sdoh_core.llm_config import (
    build_chat_model,
    build_tool_calling_agent,
    llm_content_to_text,
    llm_model,
    llm_provider,
)
from sdoh_core.requirements_file import DEFAULT_DISPLAY_PATH, RequirementsFileHelper


def _review_marker(pending: Dict[str, Any]) -> str:
    heading = pending.get("heading") or "section"
    return f"Proposed ## {heading} for review"


def _ensure_review_in_output(output: str, pending: Dict[str, Any]) -> str:
    """Keep the tool's review markdown in the chat even if the model omits it."""
    review = pending.get("review_markdown") or pending.get("proposed_full_text") or ""
    if not review.strip():
        return output
    marker = _review_marker(pending)
    if review.strip() in output or marker in output:
        return output
    path = pending.get("path", "")
    summary = pending.get("summary", "")
    return (
        f"{output.rstrip()}\n\n---\n\n"
        f"**{marker}:** `{path}`\n\n"
        f"{summary}\n\n"
        f"{review}"
    )


class ReActAgent:
    """
    Conversation shell: loads a system prompt, runs injected tools, extracts
    pending writes. Streamlit calls this agent; this agent calls the document
    tool. The file helper is not a LangChain tool.
    """

    def __init__(
        self,
        tools: Sequence[Any],
        *,
        model_name: str | None = None,
        provider: str | None = None,
        temperature: float = 0.0,
        max_iterations: int = 10,
        system_prompt_path: str = "agent_system_prompt.txt",
        documents_root: Path | None = None,
        document_tool: DocumentSectionTool | None = None,
        file_helper: RequirementsFileHelper | None = None,
        default_doc_path: str = DEFAULT_DISPLAY_PATH,
    ) -> None:
        self.provider = provider or llm_provider()
        self.model_name = model_name or llm_model(self.provider)
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.system_prompt = self._load_system_prompt(system_prompt_path)
        self.llm = build_chat_model(
            provider=self.provider,
            model_name=self.model_name,
            temperature=temperature,
        )
        self._document_tool = document_tool
        if file_helper is not None:
            self._helper = file_helper
        elif document_tool is not None:
            self._helper = document_tool.helper
        else:
            self._helper = RequirementsFileHelper(documents_root)
        self._doc_path = default_doc_path
        self._last_proposed: Dict[str, Any] | None = None
        self._this_turn_proposed: Dict[str, Any] | None = None
        self.tools: List[Any] = list(tools)
        self.agent = build_tool_calling_agent(
            self.llm,
            self.tools,
            force_tool=False,
            max_iterations=max_iterations,
            system_prompt=self.system_prompt,
        )

    def propose_section_update(self, section_body: str) -> str:
        """LangChain tool body: propose a section write, do not save."""
        if self._document_tool is None:
            raise ValueError("No document_tool configured")
        proposed = self._document_tool.propose_section(self._doc_path, section_body)
        self._this_turn_proposed = proposed
        self._last_proposed = proposed
        return self._document_tool.review_observation(proposed)

    def propose_document_update(self, user_path: str, section_body: str) -> Dict[str, Any]:
        """Used by Streamlit Save current draft; still goes through the document tool."""
        if self._document_tool is None:
            raise ValueError("No document_tool configured")
        self._doc_path = user_path
        proposed = self._document_tool.propose_section(user_path, section_body)
        self._this_turn_proposed = proposed
        self._last_proposed = proposed
        return proposed

    def apply_pending_write(self, proposed: Dict[str, Any]) -> None:
        """Streamlit Confirm: document tool applies via the helper."""
        if self._document_tool is None:
            raise ValueError("No document_tool configured")
        self._document_tool.apply_proposed_write(proposed, confirm=True)
        self._last_proposed = None

    def set_pending_write(self, proposed: Dict[str, Any] | None) -> None:
        self._last_proposed = proposed

    def discard_pending_write(self) -> None:
        self._last_proposed = None

    def _load_system_prompt(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Warning: System prompt file not found at {path}. Using empty prompt.")
            return ""

    def _document_context(self) -> str:
        path = self._doc_path
        heading = self._document_tool.heading if self._document_tool else None
        if not self._helper.exists(path):
            base = f"Working file: {path} (does not exist yet)."
        elif heading:
            current = self._document_tool.current_section(path) if self._document_tool else None
            if current:
                base = f"Working file: {path}\n\nCurrent ## {heading}:\n{current}"
            else:
                base = f"Working file: {path} exists but has no ## {heading} section yet."
        else:
            base = f"Working file: {path}."
        pending = self._last_proposed
        if not pending:
            return base
        review = pending.get("review_markdown") or pending.get("proposed_full_text") or ""
        return (
            f"{base}\n\nA proposed write is waiting for Confirm write "
            f"(not saved yet):\n{review}"
        )

    def _augment_prompt(self, user_prompt: str) -> str:
        return f"{self._document_context()}\n\nPractitioner message:\n{user_prompt}"

    def _extract_pending_write(self, result: Dict[str, Any]) -> Dict[str, Any] | None:
        pending: Dict[str, Any] | None = None
        for step in result.get("intermediate_steps") or []:
            observation = None
            if isinstance(step, (list, tuple)) and len(step) >= 2:
                observation = step[1]
            if not isinstance(observation, str):
                continue
            try:
                payload = json.loads(observation)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("type") == PROPOSED_WRITE_TYPE:
                pending = payload
        return pending

    def _history_messages(
        self,
        chat_history: Optional[List[Dict[str, str]]],
        user_prompt: str,
    ) -> List[Any]:
        messages: List[Any] = []
        for msg in chat_history or []:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user" and content == user_prompt:
                continue
            if role == "user":
                messages.append(HumanMessage(content=llm_content_to_text(content)))
            elif role == "assistant":
                messages.append(AIMessage(content=llm_content_to_text(content)))
        return messages

    def run(
        self,
        user_prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        document_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent with a user prompt and optional prior chat messages.

        Returns:
            Dict containing 'output' and 'intermediate_steps', and
            'pending_write' when the document tool proposed a save.
        """
        if document_path:
            self._doc_path = document_path
        prior_pending = self._last_proposed
        self._this_turn_proposed = None
        result = self.agent.run(
            self._augment_prompt(user_prompt),
            chat_history=self._history_messages(chat_history, user_prompt),
        )
        result["output"] = llm_content_to_text(result.get("output"))
        pending_this_turn = self._this_turn_proposed or self._extract_pending_write(
            result
        )
        if pending_this_turn:
            self._last_proposed = pending_this_turn
            result["pending_write"] = pending_this_turn
            result["output"] = _ensure_review_in_output(
                result["output"], pending_this_turn
            )
        else:
            self._last_proposed = prior_pending
        return result
