# Agent Responsibilities
These are the requirements for SDoH Assistants using the SDoH-Core-Assistant library.

# Conversation / Requirements Agent (Orchestrator)

## Responsibilities

* Owns the interaction with the practitioner (one Streamlit conversation).
* Maintains the **AI Solution Requirements Definition** as the authoritative project document (via the Document Management Tool).
* Determines the next step in the framework.
* Selects and orchestrates tools.
* Owns **consistency across all sections** of the AI Solution Requirements Definition (there is no separate Consistency Tool).
* Detects when a proposed change affects other sections:
    - Determine whether the change affects other sections.
    - Identify inconsistencies or dependencies.
    - Propose updates to the affected sections.
    - Identify those updates as dependent updates and request confirmation before writing each one.
* Requests user confirmation before updating the document.
* Produces a detailed change log after every update.

## Calls

* Tools specific to this assistant
* Document Management Tool

***

# Document Management Tool

## Purpose

Maintains the **AI Solution Requirements Definition**. This is the tool the Conversation / Requirements Agent **calls** for document operations.

## Functions

* Create sections.
* Update sections.
* Maintain document structure.
* Version control.
* Produce change log.
* Highlight pending updates.
* Compare versions.

## Uses

**File helper** (library, not a tool the orchestrator calls): path sandbox, read/write bytes, split/join markdown `##` sections. The Document Management Tool uses the helper; Streamlit may use the helper to resolve the user-chosen file path and check that the file exists. The helper does not own version control, changelogs, or compare.

## Rules

* Never overwrite automatically.
* Always request confirmation.
* Always return the proposed section text for practitioner review (not only a confirm instruction).
* Always summarize proposed changes.
* Create or update any `##` section the Conversation Agent proposes (Problem Definition and later framework sections). Do not rewrite sections the practitioner did not confirm.
* Consistency across sections is owned by the Conversation / Requirements Agent, not by this tool.


