"""Generic Streamlit chat shell for SDoH assistants.

Product copy, agents, and file helper come from AssistantAppConfig.
This module does not name framework sections.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

import streamlit as st

from sdoh_core.llm_config import llm_content_to_text


@dataclass
class AssistantAppConfig:
    title: str
    intro_message: str
    chat_placeholder: str
    file_input_label: str
    default_doc_path: str
    agent: Any
    audit_agent: Any
    file_helper: Any
    pending_review_caption: str = "The proposed section is shown in the main pane for review."
    requirements_subheader: str = "Requirements file"
    sidebar_header: str = "Controls"
    clear_history_label: str = "Clear message history"
    save_draft_label: str = "Save current draft"
    confirm_write_label: str = "Confirm write"
    cancel_label: str = "Cancel"
    proposed_file_subheader: str = "Proposed file — review before save"
    review_subheader: str = "Review"
    view_logic_steps_label: str = "🧩 View Logic Steps"
    run_audit_label: str = "🔍 Run Audit"
    logic_steps_header: str = "🧩 Logic Steps"
    audit_report_header: str = "🔍 Audit Report"
    no_steps_caption: str = "No tool calls on the last turn."
    saved_success: str = "Saved."
    no_draft_error: str = "No assistant draft to save."
    file_missing_caption: str = "File does not exist yet. Confirming a write will create it."
    propose_draft: Callable[[str, str], dict] | None = None


def escape_markdown(text: Any) -> str:
    """Escape markdown special characters but preserve tables and intentional formatting."""
    text = llm_content_to_text(text)
    text = re.sub(r"^(=+)$", r"\\\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(-+)$", r"\\\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(\*{3,})$", r"\\\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(_{3,})$", r"\\\1", text, flags=re.MULTILINE)
    text = re.sub(r"^(#{1,6})\s", r"\\\1 ", text, flags=re.MULTILINE)
    return text


def conversation_text(messages, skip_last_assistant: bool = False) -> str:
    """Flatten chat history for the audit agent."""
    rows = messages
    if skip_last_assistant and rows and rows[-1].get("role") == "assistant":
        rows = rows[:-1]
    lines = []
    for msg in rows:
        role = msg.get("role", "unknown").upper()
        lines.append(f"{role}: {llm_content_to_text(msg.get('content', ''))}")
    return "\n\n".join(lines)


def last_assistant_content(messages) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return llm_content_to_text(msg.get("content"))
    return ""


def logic_step_action(step):
    if isinstance(step, (list, tuple)) and step:
        return step[0]
    return step


def logic_step_label(step, index: int) -> str:
    action = logic_step_action(step)
    tool = getattr(action, "tool", None)
    if tool:
        return f"Step {index}: {tool}"
    if isinstance(action, dict):
        name = action.get("tool") or action.get("name") or "tool"
        return f"Step {index}: {name}"
    return f"Step {index}"


def logic_step_input(step):
    action = logic_step_action(step)
    if hasattr(action, "tool_input"):
        return action.tool_input
    if isinstance(action, dict):
        return action.get("tool_input") or action.get("input") or ""
    return ""


def logic_step_observation(step) -> str:
    if isinstance(step, (list, tuple)) and len(step) >= 2:
        return llm_content_to_text(step[1])
    return ""


def run_assistant_app(config: AssistantAppConfig) -> None:
    agent = config.agent
    audit_agent = config.audit_agent
    file_helper = config.file_helper
    propose_draft = config.propose_draft or agent.propose_document_update

    def _apply_or_discard_pending(pending, *, confirm: bool) -> None:
        if confirm:
            try:
                agent.apply_pending_write(pending)
                st.session_state["pending_write"] = None
                agent.discard_pending_write()
                st.success(config.saved_success)
                st.rerun()
            except (ValueError, OSError, PermissionError) as e:
                st.error(f"Save failed: {e}")
            return
        st.session_state["pending_write"] = None
        agent.discard_pending_write()
        st.rerun()

    def render_confirm_cancel(pending, key_prefix: str) -> None:
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            if st.button(
                config.confirm_write_label,
                type="primary",
                use_container_width=True,
                key=f"{key_prefix}_confirm",
            ):
                _apply_or_discard_pending(pending, confirm=True)
        with cancel_col:
            if st.button(
                config.cancel_label,
                use_container_width=True,
                key=f"{key_prefix}_cancel",
            ):
                _apply_or_discard_pending(pending, confirm=False)

    def render_pending_review(pending, *, key_prefix: str, show_preview: bool) -> None:
        st.warning(pending.get("summary", "Proposed file change pending confirmation."))
        st.caption(f"Will write: `{pending.get('path', '')}`")
        if show_preview:
            review = pending.get("review_markdown") or pending.get("proposed_full_text") or ""
            full = pending.get("proposed_full_text") or review
            st.markdown(review)
            with st.expander("Proposed full file (raw markdown)"):
                st.code(full, language="markdown")
        render_confirm_cancel(pending, key_prefix)

    st.header(config.title)

    if "messages" not in st.session_state:
        st.session_state["messages"] = [
            {"role": "assistant", "content": config.intro_message}
        ]
    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None
    if "show_audit" not in st.session_state:
        st.session_state["show_audit"] = False
    if "doc_path" not in st.session_state:
        st.session_state["doc_path"] = config.default_doc_path
    if "pending_write" not in st.session_state:
        st.session_state["pending_write"] = None
    if "show_steps" not in st.session_state:
        st.session_state["show_steps"] = False

    agent.set_pending_write(st.session_state.get("pending_write"))

    with st.sidebar:
        st.header(config.sidebar_header)
        st.caption(f"LLM: {agent.model_name} ({agent.provider})")

        if st.button(config.clear_history_label, use_container_width=True):
            st.session_state["messages"] = [
                {"role": "assistant", "content": config.intro_message}
            ]
            st.session_state["last_result"] = None
            st.session_state["show_audit"] = False
            st.session_state["pending_write"] = None
            st.session_state["show_steps"] = False
            agent.discard_pending_write()
            st.rerun()

        st.divider()
        st.subheader(config.requirements_subheader)
        st.text_input(config.file_input_label, key="doc_path")

        try:
            exists = file_helper.exists(st.session_state["doc_path"])
            if exists:
                saved = file_helper.last_saved(st.session_state["doc_path"])
                stamp = saved.strftime("%Y-%m-%d %H:%M UTC") if saved else "unknown"
                st.caption(f"File exists. Last saved: {stamp}")
            else:
                st.caption(config.file_missing_caption)
        except ValueError as e:
            st.error(str(e))

        if st.button(config.save_draft_label, use_container_width=True):
            draft = last_assistant_content(st.session_state["messages"])
            if not draft.strip():
                st.error(config.no_draft_error)
            else:
                try:
                    st.session_state["pending_write"] = propose_draft(
                        st.session_state["doc_path"],
                        draft,
                    )
                    st.rerun()
                except (ValueError, OSError) as e:
                    st.error(f"Could not propose a save: {e}")

        pending = st.session_state.get("pending_write")
        if pending:
            render_pending_review(pending, key_prefix="sidebar", show_preview=False)
            st.caption(config.pending_review_caption)

        if st.session_state["last_result"] is not None:
            st.divider()
            st.subheader(config.review_subheader)
            if st.button(config.view_logic_steps_label, use_container_width=True):
                st.session_state["show_steps"] = not st.session_state["show_steps"]
                st.session_state["show_audit"] = False
            if st.button(config.run_audit_label, type="secondary", use_container_width=True):
                st.session_state["show_audit"] = True
                st.session_state["show_steps"] = False

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if msg["role"] == "assistant":
                content = escape_markdown(content)
            st.markdown(content)

    pending = st.session_state.get("pending_write")
    if pending:
        st.divider()
        st.subheader(config.proposed_file_subheader)
        render_pending_review(pending, key_prefix="main", show_preview=True)

    if st.session_state["show_steps"] and st.session_state["last_result"]:
        st.divider()
        st.header(config.logic_steps_header)
        steps = st.session_state["last_result"]["result"].get("intermediate_steps") or []
        if not steps:
            st.caption(config.no_steps_caption)
        for i, step in enumerate(steps, start=1):
            with st.expander(logic_step_label(step, i), expanded=True):
                st.markdown(f"**Action Input:** `{logic_step_input(step)}`")
                obs = logic_step_observation(step)
                lines = obs.splitlines()
                if len(lines) > 12:
                    obs = "\n".join(lines[:12]) + "\n... (truncated)"
                st.code(obs)

    if st.session_state["show_audit"] and st.session_state["last_result"]:
        st.divider()
        last = st.session_state["last_result"]
        with st.spinner("Conducting audit..."):
            try:
                st.subheader(config.audit_report_header)
                audit_report = audit_agent.audit(
                    user_prompt=last["prompt"],
                    conversation=last["conversation"],
                    final_answer=last["result"].get("output", ""),
                )
                st.markdown(audit_report)
                st.caption(f"*Audited by: {audit_agent.display_name()}*")
            except Exception as e:
                st.error(f"Audit failed: {e}")

    prompt = st.chat_input(config.chat_placeholder)

    if prompt:
        st.session_state["show_audit"] = False
        st.session_state["show_steps"] = False
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.spinner("Processing..."):
            try:
                result = agent.run(
                    prompt,
                    chat_history=st.session_state.messages,
                    document_path=st.session_state["doc_path"],
                )
                output = llm_content_to_text(result.get("output", ""))
                if result.get("pending_write"):
                    st.session_state["pending_write"] = result["pending_write"]

                st.session_state["last_result"] = {
                    "prompt": prompt,
                    "conversation": conversation_text(
                        st.session_state.messages, skip_last_assistant=True
                    ),
                    "result": result,
                }
                st.session_state.messages.append(
                    {"role": "assistant", "content": output}
                )
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
