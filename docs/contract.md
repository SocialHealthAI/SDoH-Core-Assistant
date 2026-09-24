# Welcome message (opening chat bubble)

Core’s Streamlit shell shows one assistant message when a chat session **starts** and when the practitioner clicks **Clear message history**. Core does **not** write product copy or know framework section names. Each assistant builds the greeting.

## What Core does

`AssistantAppConfig` fields:

| Field | Role |
| ----- | ---- |
| `intro_message` | Required fallback string. Used if `intro_builder` is omitted, returns empty, or raises `OSError` / `ValueError` / `TypeError`. |
| `intro_builder` | Optional `Callable[[str], str]`. Argument is the current sidebar file path (`doc_path`). |

`opening_assistant_message(config, doc_path)` picks the builder result or the fallback. `run_assistant_app` calls it:

- on first visit (`messages` not yet in session state), after `doc_path` is initialized to `default_doc_path`
- on **Clear message history**, using the path currently in the sidebar (also drops chat and any pending Confirm)
- on **Reload file from disk**, using the path currently in the sidebar (replaces only the first bubble; does **not** write the file and does **not** apply Confirm)

An existing browser session keeps its old first bubble until Reload, Clear message history, or a refresh that drops session state.

Chat is not a new session when they only change the file path. Use **Reload file from disk** (or clear history) after they switch files, or they will still see the previous opening text. If a proposed write is waiting, Reload keeps it and warns that Confirm would overwrite the current disk file.

## What each assistant should say

Keep it **very brief** (about four sentences):

1. **Welcome.**
2. **How this assistant helps** (this product’s job only—interview, draft its section, tools it owns, confirm-before-write).
3. **If the requirements file exists:** we are **continuing with that document** (show the path) and a **short summary** of *this assistant’s* `##` section.
4. **If the file does not exist:** say so and how to start. **If the file exists but the section is empty or a placeholder:** say we are continuing with the path and that the section is still empty.

Do **not** dump the full section or an empty 10-heading template. Do **not** call an LLM for the greeting (first paint must stay fast and must not require a provider). Read the file with `RequirementsFileHelper` and this product’s `DocumentSectionTool` binding.

## How to wire it

Product-owned module (example name `welcome_message.py`), not Core:

```python
def build_welcome_message(doc_path: str, file_helper, document_tool) -> str:
    help_text = (
        "Welcome. I help you …"  # this assistant only
    )
    if not file_helper.exists(doc_path):
        return (
            f"{help_text} There is no requirements file at `{doc_path}` yet. "
            "Describe the work to begin."
        )
    body = document_tool.current_section(doc_path)
    summary = first_usable_paragraph(body)  # skip headings and "to be defined"
    continuing = f"We are continuing with `{doc_path}`."
    if summary:
        return f"{help_text} {continuing} {summary}"
    return (
        f"{help_text} {continuing} "
        "The section in that file is still empty or a placeholder."
    )
```

Pass it into the shell:

```python
def intro_for_path(doc_path: str) -> str:
    return build_welcome_message(doc_path, file_helper, document_tool)

run_assistant_app(
    AssistantAppConfig(
        intro_message="How can I help?",  # fallback
        intro_builder=intro_for_path,
        # title, tools, default_doc_path, …
    )
)
```

Use the **same** `RequirementsFileHelper` instance as the rest of the app. The document tool must be bound to **this** assistant’s heading (Problem Definition, Data Inventory, …). Clip the summary to a couple of sentences.

## Rules

- Product copy and section summaries stay in the product repo. Core stays generic.
- `intro_builder` must be a pure function of `doc_path` (and files on disk). No Streamlit calls inside it.
- Unit-test the builder with `tmp_path`: missing file, placeholder section, real summary. Do not hit the network.
