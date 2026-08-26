"""Unit tests for Streamlit helper formatters. Does not run Streamlit."""
from sdoh_core.streamlit_app import (
    AssistantAppConfig,
    conversation_text,
    escape_markdown,
    last_assistant_content,
    logic_step_input,
    logic_step_label,
    logic_step_observation,
    run_assistant_app,
)


def test_escape_markdown_escapes_heading_prefix():
    assert escape_markdown("# Title").startswith("\\# ")


def test_conversation_text_skips_last_assistant():
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    text = conversation_text(messages, skip_last_assistant=True)

    assert "USER: Hello" in text
    assert "Hi" not in text


def test_last_assistant_content_returns_latest():
    messages = [
        {"role": "assistant", "content": "first"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "second"},
    ]

    assert last_assistant_content(messages) == "second"


def test_logic_step_label_uses_tool_name():
    step = ({"tool": "example_tool", "tool_input": {"x": 1}}, "ok")

    assert logic_step_label(step, 1) == "Step 1: example_tool"
    assert logic_step_input(step) == {"x": 1}
    assert logic_step_observation(step) == "ok"


def test_assistant_app_config_has_required_fields():
    config = AssistantAppConfig(
        title="Test",
        intro_message="Hello",
        chat_placeholder="Type here",
        file_input_label="File location",
        default_doc_path="sdoh_documents/file.md",
        agent=object(),
        audit_agent=object(),
        file_helper=object(),
    )

    assert config.title == "Test"
    assert callable(run_assistant_app)
    assert "Problem Definition" not in config.title
    assert "Problem Definition" not in (config.pending_review_caption or "")
