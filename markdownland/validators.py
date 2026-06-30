"""Pre-flight validation for markdown headed to a *published* document.

Things that look fine in a GitHub README quietly break once the same markdown
becomes a standalone PDF/HTML: relative links point nowhere, local images
don't travel with the file, heading levels skip, anchors collide. These checks
surface those problems before the user hits download.

Each check yields :class:`Finding` objects with a 1-based line number so the UI
can point right at the offending line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote

# Severity ordering for sorting/summaries.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    line: int
    severity: str  # "error" | "warning" | "info"
    rule: str  # short stable id, e.g. "relative-link"
    message: str
    snippet: str = ""


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"error": 0, "warning": 0, "info": 0}
        for f in self.findings:
            out[f.severity] += 1
        return out

    @property
    def ok(self) -> bool:
        return not any(f.severity in ("error", "warning") for f in self.findings)


# A URL target that resolves anywhere — anything else is "local" and won't
# survive being moved into a published artifact.
_ABSOLUTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#|data:|mailto:|tel:)", re.I)

# Inline links/images: ![alt](target) and [text](target). Captures whether it
# was an image (leading !), the bracket text, and the parenthesised target.
_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+[\"'][^\"']*[\"'])?\s*\)")

# Obsidian-style wikilinks: [[Page]], [[Page|Alias]], and embeds ![[file]].
# These render as literal text in standard markdown / PDF / HTML.
_WIKILINK = re.compile(r"(!?)\[\[\s*([^\[\]]+?)\s*\]\]")

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HEADING_ID = re.compile(r"\s*\{[^}]*#([A-Za-z0-9_.:-]+)[^}]*\}\s*$")
_FENCE = re.compile(r"^\s*(```+|~~~+)")
_TODO = re.compile(r"\b(TODO|FIXME|XXX)\b")
_BARE_URL = re.compile(r"(?<![(<\"'\]=])\bhttps?://[^\s)>\]]+")
_TITLE_META = re.compile(r"^\s*title\s*[:=]\s*(.+?)\s*$", re.I)
_HTML_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9:-]*(?:\s[^>]*)?/?>")
_DANGEROUS_HTML = re.compile(r"<\s*/?\s*(script|iframe|object|embed)\b", re.I)


def _slug(text: str) -> str:
    """Approximate pandoc/GitHub heading-anchor slugging for collision checks."""
    text = re.sub(r"[`*_~]", "", text.lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s]+", "-", text.strip())


def _is_local(target: str) -> bool:
    return not _ABSOLUTE.match(target.strip())


def _frontmatter(lines: list[str]) -> tuple[set[int], bool]:
    """Return line numbers occupied by frontmatter, plus whether it has a title."""
    if not lines or lines[0].strip() not in {"---", "+++"}:
        return set(), False

    marker = lines[0].strip()
    for offset, line in enumerate(lines[1:], start=2):
        if line.strip() != marker:
            continue
        block = lines[1 : offset - 1]
        skipped = set(range(1, offset + 1))
        has_title = any(_metadata_value(line) for line in block)
        return skipped, has_title
    return set(), False


def _metadata_value(line: str) -> str:
    match = _TITLE_META.match(line)
    if not match:
        return ""
    value = match.group(1).strip().strip("\"'")
    return value


def _heading_title_and_id(raw_title: str) -> tuple[str, str | None]:
    """Split a heading title from a Pandoc-style explicit id, if present."""
    match = _HEADING_ID.search(raw_title)
    if not match:
        return raw_title.strip(), None
    return raw_title[: match.start()].strip(), match.group(1)


def validate(source: str) -> Report:
    findings: list[Finding] = []
    lines = source.splitlines()
    frontmatter_lines, metadata_has_title = _frontmatter(lines)

    in_fence = False
    fence_marker = ""
    heading_levels: list[tuple[int, int]] = []  # (line, level)
    seen_anchors: dict[str, int] = {}
    anchor_refs: list[tuple[int, str, str]] = []  # (line, anchor, snippet)
    has_h1 = False

    for i, line in enumerate(lines, start=1):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                in_fence = False
            continue
        if in_fence:
            continue
        if i in frontmatter_lines:
            continue

        # --- links & images ---------------------------------------------------
        for m in _LINK.finditer(line):
            is_image = m.group(1) == "!"
            text, target = m.group(2), m.group(3)
            snippet = m.group(0)
            if is_image:
                if _is_local(target):
                    findings.append(
                        Finding(
                            i,
                            "error",
                            "local-image",
                            f"Image “{target}” is a local path — it won't be embedded "
                            "in the published file. Use a full URL or a data: URI.",
                            snippet,
                        )
                    )
                if not text.strip():
                    findings.append(
                        Finding(
                            i,
                            "warning",
                            "image-alt",
                            "Image has no alt text (hurts accessibility & PDF a11y).",
                            snippet,
                        )
                    )
            else:
                if _is_local(target) and not target.startswith("#"):
                    findings.append(
                        Finding(
                            i,
                            "warning",
                            "relative-link",
                            f"Link to “{target}” is relative — it will break once the "
                            "document is published elsewhere. Use an absolute URL.",
                            snippet,
                        )
                    )
                if target.startswith("#"):
                    anchor = unquote(target[1:]).strip()
                    if anchor:
                        anchor_refs.append((i, anchor, snippet))
                    else:
                        findings.append(
                            Finding(
                                i,
                                "info",
                                "empty-anchor",
                                "Link points to “#” without a destination anchor.",
                                snippet,
                            )
                        )
                if not text.strip():
                    findings.append(
                        Finding(
                            i, "warning", "empty-link-text", "Link has no visible text.", snippet
                        )
                    )

        # --- wikilinks (Obsidian-style) --------------------------------------
        for m in _WIKILINK.finditer(line):
            inner = m.group(2).strip()
            if m.group(1) == "!":
                msg = (
                    f"Wikilink embed “![[{inner}]]” is Obsidian-only — it "
                    "won't embed in published output. Use ![alt](url)."
                )
            else:
                msg = (
                    f"Wikilink “[[{inner}]]” is Obsidian/wiki syntax — it "
                    "renders as literal text outside a wiki. Use a "
                    "[label](url) link."
                )
            findings.append(Finding(i, "warning", "wikilink", msg, m.group(0)))

        # --- headings ---------------------------------------------------------
        hm = _HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            title, explicit_id = _heading_title_and_id(hm.group(2))
            heading_levels.append((i, level))
            has_h1 = has_h1 or level == 1
            anchor = explicit_id or _slug(title)
            if anchor:
                if anchor in seen_anchors:
                    findings.append(
                        Finding(
                            i,
                            "warning",
                            "duplicate-heading",
                            f"Heading “{title}” collides with the anchor from "
                            f"line {seen_anchors[anchor]} (#{anchor}).",
                            line.strip(),
                        )
                    )
                else:
                    seen_anchors[anchor] = i

        # --- misc -------------------------------------------------------------
        if _TODO.search(line):
            findings.append(
                Finding(i, "info", "todo-marker", "Leftover TODO/FIXME/XXX marker.", line.strip())
            )
        if _BARE_URL.search(line):
            findings.append(
                Finding(
                    i,
                    "info",
                    "bare-url",
                    "Bare URL — wrap it in <…> or [text](…) so every renderer links it.",
                    line.strip(),
                )
            )
        if _DANGEROUS_HTML.search(line):
            findings.append(
                Finding(
                    i,
                    "error",
                    "dangerous-html",
                    "Raw embed/script HTML can execute or be stripped in published output.",
                    line.strip(),
                )
            )
        elif _HTML_TAG.search(line):
            findings.append(
                Finding(
                    i,
                    "warning",
                    "raw-html",
                    "Raw HTML may not survive PDF, DOCX, EPUB, or non-HTML exports.",
                    line.strip(),
                )
            )

    # --- document-level checks ------------------------------------------------
    if in_fence:
        findings.append(
            Finding(
                len(lines) or 1,
                "error",
                "unclosed-fence",
                "Unclosed code fence — the rest of the document is swallowed as code.",
            )
        )

    if heading_levels and not has_h1 and not metadata_has_title:
        findings.append(
            Finding(
                heading_levels[0][0],
                "info",
                "no-title",
                "No level-1 heading — the published PDF/HTML may lack a title.",
            )
        )

    for line, anchor, snippet in anchor_refs:
        if anchor not in seen_anchors:
            findings.append(
                Finding(
                    line,
                    "warning",
                    "missing-anchor",
                    f"Link points to #{anchor}, but no matching heading anchor was found.",
                    snippet,
                )
            )

    prev = 0
    for ln, level in heading_levels:
        if prev and level > prev + 1:
            findings.append(
                Finding(
                    ln,
                    "warning",
                    "heading-skip",
                    f"Heading jumps from H{prev} to H{level}; outlines and PDF "
                    "bookmarks expect one level at a time.",
                )
            )
        prev = level

    findings.sort(key=lambda f: (f.line, SEVERITY_ORDER[f.severity]))
    return Report(findings)
