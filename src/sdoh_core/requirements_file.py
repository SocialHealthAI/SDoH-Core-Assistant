"""
Mechanical persistence for the AI Solution Requirements Definition.

Library, not a LangChain tool and not the Document Management Tool.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_RELATIVE_FILE = "ai-solution-requirements-definition.md"
DEFAULT_DISPLAY_PATH = f"sdoh_documents/{DEFAULT_RELATIVE_FILE}"
DEFAULT_DOCUMENT_TITLE = "# AI Solution Requirements Definition"
HOST_ROOT_ALIASES = ("sdoh_documents", "documents")

_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)


def _strip_host_root_alias(rel: str) -> str:
    for alias in HOST_ROOT_ALIASES:
        if rel == alias or rel == f"{alias}/":
            raise ValueError(f"Choose a file inside {alias}/, not the folder itself")
        prefix = f"{alias}/"
        if rel.startswith(prefix):
            return rel[len(prefix) :]
    return rel


@dataclass(frozen=True)
class MarkdownSection:
    heading: str
    body: str


def default_documents_root() -> Path:
    """Container `/documents` when mounted; otherwise sibling `sdoh_documents/`."""
    env = os.environ.get("DOCUMENTS_ROOT")
    if env:
        return Path(env)
    container = Path("/documents")
    if container.is_dir():
        return container
    # src/sdoh_core/this_file.py → Core repo → parent installs/sdoh_documents
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root.parent / "sdoh_documents"


class RequirementsFileHelper:
    """Path sandbox, markdown `##` split/join, and confirm-gated writes."""

    def __init__(self, documents_root: Path | None = None) -> None:
        self.root = (documents_root or default_documents_root()).resolve()

    def resolve(self, user_path: str) -> Path:
        if user_path is None:
            raise ValueError("Path is required")
        if "\x00" in user_path:
            raise ValueError("Invalid path")
        raw = user_path.strip().replace("\\", "/")
        if not raw:
            raise ValueError("Path is empty")

        root = self.root.resolve()
        as_path = Path(raw)
        if as_path.is_absolute() or raw.startswith("/"):
            candidate = Path(raw).resolve()
        else:
            rel = _strip_host_root_alias(raw)
            if not rel:
                raise ValueError("Path is empty")
            candidate = (root / rel).resolve()

        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Path is outside the documents directory") from exc
        return candidate

    def relative_posix(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    def exists(self, user_path: str) -> bool:
        return self.resolve(user_path).is_file()

    def last_saved(self, user_path: str) -> datetime | None:
        path = self.resolve(user_path)
        if not path.is_file():
            return None
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    def fingerprint(self, user_path: str) -> dict[str, Any]:
        """Snapshot used to detect out-of-band edits before Confirm write."""
        path = self.resolve(user_path)
        if not path.is_file():
            return {"exists": False, "mtime_ns": None, "sha256": None}
        data = path.read_bytes()
        return {
            "exists": True,
            "mtime_ns": path.stat().st_mtime_ns,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def read(self, user_path: str) -> str:
        path = self.resolve(user_path)
        return path.read_text(encoding="utf-8")

    def write(self, user_path: str, content: str, *, confirm: bool) -> Path:
        if not confirm:
            raise PermissionError("Refusing to write without confirm=True")
        path = self.resolve(user_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def parse(self, text: str) -> tuple[str, list[MarkdownSection]]:
        if not text:
            return "", []
        matches = list(_HEADING.finditer(text))
        if not matches:
            return text, []
        preamble = text[: matches[0].start()].rstrip("\n")
        sections: list[MarkdownSection] = []
        for i, match in enumerate(matches):
            heading = match.group(1).strip()
            body_start = match.end()
            if body_start < len(text) and text[body_start] == "\n":
                body_start += 1
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[body_start:body_end].rstrip("\n")
            sections.append(MarkdownSection(heading=heading, body=body))
        return preamble, sections

    def render(self, preamble: str, sections: list[MarkdownSection]) -> str:
        parts: list[str] = []
        pre = preamble.rstrip()
        if pre:
            parts.append(pre)
        for section in sections:
            block = f"## {section.heading}"
            body = section.body.strip("\n")
            if body:
                block = f"{block}\n\n{body}"
            parts.append(block)
        return "\n\n".join(parts) + "\n"
