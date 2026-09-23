"""
Document Management Tool: one `##` section of the AI Solution Requirements Definition.

Products bind heading (e.g. "2. Data Inventory") and optional matcher.
The Conversation Agent calls this; the file helper is not a LangChain tool.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sdoh_core.requirements_file import (
    DEFAULT_DOCUMENT_TITLE,
    MarkdownSection,
    RequirementsFileHelper,
)

PROPOSED_WRITE_TYPE = "proposed_write"
FILE_CHANGED_ON_DISK = (
    "The requirements file changed on disk after this proposal. "
    "Cancel, then propose again so we re-read the file. "
    "Confirming now would overwrite those edits."
)

HeadingMatch = Callable[[str], bool]


def heading_number(heading: str) -> int | None:
    match = re.match(r"^(\d+)", heading.strip())
    return int(match.group(1)) if match else None


def default_heading_match(canonical: str, heading: str) -> bool:
    c = canonical.strip().lower()
    h = heading.strip().lower()
    if h == c:
        return True
    c_rest = re.sub(r"^\d+[.)]?\s*", "", c)
    h_rest = re.sub(r"^\d+[.)]?\s*", "", h)
    if not c_rest or h_rest != c_rest:
        return False
    c_num = heading_number(canonical)
    h_num = heading_number(heading)
    return h_num is None or c_num is None or h_num == c_num


class DocumentSectionTool:
    """Create/update one numbered `##` section after confirmation."""

    def __init__(
        self,
        helper: RequirementsFileHelper,
        *,
        heading: str,
        heading_match: HeadingMatch | None = None,
    ) -> None:
        self.helper = helper
        self.heading = heading.strip()
        self._heading_match = heading_match

    def matches_heading(self, heading: str) -> bool:
        if self._heading_match:
            return self._heading_match(heading)
        return default_heading_match(self.heading, heading)

    def current_section(self, user_path: str) -> str | None:
        if not self.helper.exists(user_path):
            return None
        _preamble, sections = self.helper.parse(self.helper.read(user_path))
        for section in sections:
            if self.matches_heading(section.heading):
                return section.body
        return None

    def propose_section(self, user_path: str, section_body: str) -> dict[str, Any]:
        existing = self.helper.read(user_path) if self.helper.exists(user_path) else ""
        proposed = self._splice_section(existing, section_body)
        creating = not existing
        summary = (
            f"Create `{user_path}` with section ## {self.heading}."
            if creating
            else (
                f"Replace ## {self.heading} in `{user_path}`. "
                "Other ## sections will be left unchanged."
            )
        )
        return {
            "type": PROPOSED_WRITE_TYPE,
            "path": user_path,
            "summary": summary,
            "heading": self.heading,
            "review_markdown": self._section_review(section_body),
            "proposed_full_text": proposed,
            "baseline": self.helper.fingerprint(user_path),
            "wrote": False,
        }

    def review_observation(self, proposed: dict[str, Any]) -> str:
        path = proposed.get("path", "")
        summary = proposed.get("summary", "")
        heading = proposed.get("heading") or self.heading
        review = proposed.get("review_markdown") or proposed.get("proposed_full_text") or ""
        return (
            "PROPOSED WRITE — not saved until the practitioner clicks Confirm write "
            "(or Cancel to discard).\n\n"
            f"Path: {path}\n"
            f"{summary}\n\n"
            f"Proposed ## {heading} for review:\n\n"
            f"{review}"
        )

    def apply_proposed_write(self, proposed: dict[str, Any], *, confirm: bool) -> None:
        if proposed.get("type") != PROPOSED_WRITE_TYPE:
            raise ValueError("Not a proposed write")
        path = proposed.get("path")
        text = proposed.get("proposed_full_text")
        if not path or not isinstance(text, str):
            raise ValueError("Proposed write is missing path or text")
        if confirm:
            self._reject_if_file_changed(proposed)
        self.helper.write(path, text, confirm=confirm)

    def _reject_if_file_changed(self, proposed: dict[str, Any]) -> None:
        baseline = proposed.get("baseline")
        path = proposed.get("path")
        if not isinstance(baseline, dict) or not path:
            return
        current = self.helper.fingerprint(path)
        if baseline.get("sha256") != current.get("sha256"):
            raise ValueError(FILE_CHANGED_ON_DISK)

    def _section_review(self, section_body: str) -> str:
        body = section_body.strip("\n")
        if not body:
            return f"## {self.heading}\n"
        return f"## {self.heading}\n\n{body}\n"

    def _splice_section(self, existing: str, section_body: str) -> str:
        preamble, sections = self.helper.parse(existing)
        if not preamble.strip():
            preamble = DEFAULT_DOCUMENT_TITLE
        body = section_body.strip("\n")
        replacement = MarkdownSection(heading=self.heading, body=body)
        found = False
        kept: list[MarkdownSection] = []
        for section in sections:
            if self.matches_heading(section.heading):
                kept.append(replacement)
                found = True
            else:
                kept.append(section)
        if not found:
            kept = self._insert_section(kept, replacement)
        return self.helper.render(preamble, kept)

    def _insert_section(
        self,
        sections: list[MarkdownSection],
        replacement: MarkdownSection,
    ) -> list[MarkdownSection]:
        new_num = heading_number(replacement.heading)
        if new_num is None:
            return [*sections, replacement]
        ordered: list[MarkdownSection] = []
        inserted = False
        for section in sections:
            other_num = heading_number(section.heading)
            if (
                not inserted
                and other_num is not None
                and other_num > new_num
            ):
                ordered.append(replacement)
                inserted = True
            ordered.append(section)
        if not inserted:
            ordered.append(replacement)
        return ordered
