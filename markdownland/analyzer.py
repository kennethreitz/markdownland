"""Lightweight document intelligence for markdownland.

The app already asks pandoc for faithful rendering. This module provides the
fast local facts a publishing workbench wants on every keystroke: title,
outline, counts, and reading-time estimates. It is deliberately heuristic and
keeps the rules close to the validator's view of Markdown.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Heading:
    line: int
    level: int
    title: str
    anchor: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentStats:
    lines: int
    words: int
    characters: int
    reading_minutes: int
    headings: int
    links: int
    images: int
    code_blocks: int
    tables: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentAnalysis:
    title: str
    stats: DocumentStats
    outline: list[Heading]

    def as_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "stats": self.stats.as_dict(),
            "outline": [h.as_dict() for h in self.outline],
        }


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HEADING_ID = re.compile(r"\s*\{[^}]*#([A-Za-z0-9_.:-]+)[^}]*\}\s*$")
_FENCE = re.compile(r"^\s*(```+|~~~+)")
_INLINE_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")
_REFERENCE_LINK = re.compile(r"(!?)\[[^\]]+\]\[[^\]]*\]")
_TITLE_META = re.compile(r"^\s*title\s*[:=]\s*(.+?)\s*$", re.I)
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'_-]*")


def analyze(source: str) -> DocumentAnalysis:
    lines = source.splitlines()
    frontmatter_lines, metadata_title = _frontmatter(lines)
    prose_lines: list[str] = []
    table_candidate_lines: set[int] = set()
    outline: list[Heading] = []
    links = images = code_blocks = 0

    in_fence = False
    fence_marker = ""

    for number, line in enumerate(lines, start=1):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
                code_blocks += 1
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                in_fence = False
            continue

        if in_fence or number in frontmatter_lines:
            continue

        heading = _heading(line, number)
        if heading:
            outline.append(heading)

        for match in _INLINE_LINK.finditer(line):
            if match.group(1) == "!":
                images += 1
            else:
                links += 1
        for match in _REFERENCE_LINK.finditer(line):
            if match.group(1) == "!":
                images += 1
            else:
                links += 1

        if "|" in line:
            table_candidate_lines.add(number)
        prose_lines.append(_strip_markup(line))

    words = len(_WORD.findall("\n".join(prose_lines)))
    title = metadata_title or _first_h1(outline) or (outline[0].title if outline else "Untitled")
    stats = DocumentStats(
        lines=len(lines),
        words=words,
        characters=len(source),
        reading_minutes=math.ceil(words / 225) if words else 0,
        headings=len(outline),
        links=links,
        images=images,
        code_blocks=code_blocks,
        tables=_count_tables(lines, table_candidate_lines, frontmatter_lines),
    )
    return DocumentAnalysis(title=title, stats=stats, outline=outline)


def _frontmatter(lines: list[str]) -> tuple[set[int], str]:
    if not lines or lines[0].strip() not in {"---", "+++"}:
        return set(), ""

    marker = lines[0].strip()
    for offset, line in enumerate(lines[1:], start=2):
        if line.strip() != marker:
            continue
        body = lines[1 : offset - 1]
        return set(range(1, offset + 1)), _metadata_title(body)
    return set(), ""


def _metadata_title(lines: list[str]) -> str:
    for line in lines:
        match = _TITLE_META.match(line)
        if match:
            return match.group(1).strip().strip("\"'")
    return ""


def _heading(line: str, number: int) -> Heading | None:
    match = _HEADING.match(line)
    if not match:
        return None
    title, explicit_id = _heading_title_and_id(match.group(2))
    anchor = explicit_id or _slug(title)
    return Heading(line=number, level=len(match.group(1)), title=title, anchor=anchor)


def _heading_title_and_id(raw_title: str) -> tuple[str, str | None]:
    match = _HEADING_ID.search(raw_title)
    if not match:
        return raw_title.strip(), None
    return raw_title[: match.start()].strip(), match.group(1)


def _first_h1(outline: list[Heading]) -> str:
    for heading in outline:
        if heading.level == 1:
            return heading.title
    return ""


def _slug(text: str) -> str:
    text = re.sub(r"[`*_~]", "", text.lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s]+", "-", text.strip())


def _strip_markup(line: str) -> str:
    line = _INLINE_LINK.sub(r"\2", line)
    line = _REFERENCE_LINK.sub("", line)
    line = re.sub(r"`[^`]*`", "", line)
    line = re.sub(r"<[^>]+>", "", line)
    line = re.sub(r"^[#>\s-]+", "", line)
    return line


def _count_tables(lines: list[str], candidates: set[int], skip: set[int]) -> int:
    tables = 0
    in_table = False
    for idx, line in enumerate(lines, start=1):
        if idx in skip:
            continue
        prev_line = lines[idx - 2] if idx >= 2 else ""
        next_line = lines[idx] if idx < len(lines) else ""
        is_table_line = idx in candidates and (
            _TABLE_SEPARATOR.match(line)
            or _TABLE_SEPARATOR.match(prev_line)
            or _TABLE_SEPARATOR.match(next_line)
        )
        if is_table_line and not in_table:
            tables += 1
            in_table = True
        elif not is_table_line:
            in_table = False
    return tables
