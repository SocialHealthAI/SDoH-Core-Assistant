# SDoH-Core-Assistant

Shared library (`sdoh_core`) for SDoH Streamlit assistants: LLM factory (OpenAI and Anthropic), tool-calling loop, confirm-before-write document sections, audit runner, and chat shell.

This repo is **not** a running assistant. Product apps (for example the Problem Definition Assistant) import it and pass their own tools and prompts.

## Consume during development (path)

Sibling checkout next to the product repo:

```
C:\installs\SDoH-Core-Assistant
C:\installs\SDoH-AI-Problem-Definition-Assistant
C:\installs\sdoh_documents
```

Product Poetry:

```toml
sdoh-core = { path = "../SDoH-Core-Assistant", develop = true }
```

Docker Compose on the product: bind-mount this repo and set `PYTHONPATH=/opt/sdoh-core/src` so Core Python edits apply without rebuilding the image.

## Consume later (Git URL)

After this package has a remote and a version tag:

```toml
sdoh-core = { git = "<github-url-of-SDoH-Core-Assistant>", tag = "v0.1.0" }
```

Then rebuild the product image. Private repos need Docker git credentials (do not bake a PAT into the image).

## Layout

```
src/sdoh_core/     # importable package
tests/unit/        # pytest; no live LLM calls
docs/              # how product assistants use Core
```

## Opening welcome message

Each product assistant owns the first chat bubble (welcome, how it helps, optional recap of the current requirements file). Core only calls an optional `intro_builder(doc_path)` or falls back to `intro_message`.

See [docs/contract.md](docs/contract.md) for the welcome builder. See [docs/Agent Responsibilities.md](docs/Agent Responsibilities.md) for orchestrator and document-management requirements that product assistants must follow.

## Tests

From this repo (with Poetry or `PYTHONPATH=src`):

```
pytest tests/unit -q
```
