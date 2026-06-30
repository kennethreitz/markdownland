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

# Severity ordering for sorting/summaries.
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    line: int
    severity: str          # "error" | "warning" | "info"
    rule: str              # short stable id, e.g. "relative-link"
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

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```+|~~~+)")
_TODO = re.compile(r"\b(TODO|FIXME|XXX)\b")
_BARE_URL = re.compile(r"(?<![(<\"'\]=])\bhttps?://[^\s)>\]]+")


def _slug(text: str) -> str:
    """Approximate pandoc/GitHub heading-anchor slugging for collision checks."""
    text = re.sub(r"[`*_~]", "", text.lower())
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s]+", "-", text.strip())


def _is_local(target: str) -> bool:
    return not _ABSOLUTE.match(target.strip())


def validate(source: str) -> Report:
    findings: list[Finding] = []
    lines = source.splitlines()

    in_fence = False
    fence_marker = ""
    heading_levels: list[tuple[int, int]] = []   # (line, level)
    seen_slugs: dict[str, int] = {}
    has_h1 = False

    for i, line in enumerate(lines, start=1):
        fence = _FENCE.match(line)
        if fence:
            marker = fence.group(1)[0] * 3
            if not in_fence:
                in_fence, fence_marker = True, marker
            elif line.strip().startswith(fence_marker):
                in_fence = False
            continue
        if in_fence:
            continue

        # --- links & images ---------------------------------------------------
        for m in _LINK.finditer(line):
            is_image = m.group(1) == "!"
            text, target = m.group(2), m.group(3)
            snippet = m.group(0)
            if is_image:
                if _is_local(target):
                    findings.append(Finding(
                        i, "error", "local-image",
                        f"Image “{target}” is a local path — it won't be embedded "
                        "in the published file. Use a full URL or a data: URI.",
                        snippet))
                if not text.strip():
                    findings.append(Finding(
                        i, "warning", "image-alt",
                        "Image has no alt text (hurts accessibility & PDF a11y).",
                        snippet))
            else:
                if _is_local(target) and not target.startswith("#"):
                    findings.append(Finding(
                        i, "warning", "relative-link",
                        f"Link to “{target}” is relative — it will break once the "
                        "document is published elsewhere. Use an absolute URL.",
                        snippet))
                if not text.strip():
                    findings.append(Finding(
                        i, "warning", "empty-link-text",
                        "Link has no visible text.", snippet))

        # --- headings ---------------------------------------------------------
        hm = _HEADING.match(line)
        if hm:
            level = len(hm.group(1))
            title = hm.group(2)
            heading_levels.append((i, level))
            has_h1 = has_h1 or level == 1
            slug = _slug(title)
            if slug:
                if slug in seen_slugs:
                    findings.append(Finding(
                        i, "warning", "duplicate-heading",
                        f"Duplicate heading “{title}” collides with the anchor from "
                        f"line {seen_slugs[slug]} (#{slug}).", line.strip()))
                else:
                    seen_slugs[slug] = i

        # --- misc -------------------------------------------------------------
        if _TODO.search(line):
            findings.append(Finding(
                i, "info", "todo-marker",
                "Leftover TODO/FIXME/XXX marker.", line.strip()))
        if _BARE_URL.search(line):
            findings.append(Finding(
                i, "info", "bare-url",
                "Bare URL — wrap it in <…> or [text](…) so every renderer links it.",
                line.strip()))

    # --- document-level checks ------------------------------------------------
    if in_fence:
        findings.append(Finding(
            len(lines) or 1, "error", "unclosed-fence",
            "Unclosed code fence — the rest of the document is swallowed as code."))

    if heading_levels and not has_h1:
        findings.append(Finding(
            heading_levels[0][0], "info", "no-title",
            "No level-1 heading — the published PDF/HTML may lack a title."))

    prev = 0
    for ln, level in heading_levels:
        if prev and level > prev + 1:
            findings.append(Finding(
                ln, "warning", "heading-skip",
                f"Heading jumps from H{prev} to H{level}; outlines and PDF "
                "bookmarks expect one level at a time."))
        prev = level

    findings.sort(key=lambda f: (f.line, SEVERITY_ORDER[f.severity]))
    return Report(findings)
