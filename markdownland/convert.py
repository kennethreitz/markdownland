"""Conversion engine for markdownland.

Thin, well-behaved wrappers around ``pandoc`` (and ``tectonic`` for PDF). All
conversions read the source markdown from stdin and write to stdout (text
formats) or to a temp file (binary formats), so nothing ever touches a shell.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Pandoc's extended markdown is the richest reader (tables, math, footnotes,
# definition lists, ...). ``tex_math_dollars`` lets people write $x^2$ math.
INPUT_FORMAT = "markdown+tex_math_dollars+emoji"

PANDOC = shutil.which("pandoc")
TECTONIC = shutil.which("tectonic")
PDFTOTEXT = shutil.which("pdftotext")  # poppler, for PDF import (pandoc can't read PDF)

# How long any single conversion may run before we give up (seconds). PDF gets
# a longer leash because tectonic may fetch LaTeX packages on first use.
TEXT_TIMEOUT = 30
PDF_TIMEOUT = 120

_TITLE_META = re.compile(r"^\s*title\s*[:=]\s*(.+?)\s*$", re.I)
_H1 = re.compile(r"^#\s+(.*?)\s*#*\s*$", re.M)
_HEADING_ID = re.compile(r"\s*\{[^}]*#[A-Za-z0-9_.:-]+[^}]*\}\s*$")

_TEXT_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd", ".txt", ".text"}
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ConversionError(RuntimeError):
    """Raised when pandoc/tectonic fails. ``message`` is safe to show a user."""


class ToolMissingError(ConversionError):
    """A required external binary (pandoc/tectonic) isn't installed."""


@dataclass(frozen=True)
class TextFormat:
    """A text output format, e.g. HTML or reStructuredText."""

    key: str           # stable id used in URLs/buttons
    label: str         # human label for the UI
    pandoc_to: str     # pandoc writer name
    extension: str     # download file extension
    mimetype: str      # for downloads / clipboard
    standalone: bool = False   # pass pandoc -s (full document vs. fragment)
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class BinaryFormat:
    """A binary output format produced via a temp file (PDF, DOCX, ...)."""

    key: str
    label: str
    extension: str
    mimetype: str
    pandoc_to: str | None = None     # None => pandoc infers from extension
    extra_args: tuple[str, ...] = ()
    needs_tectonic: bool = False


# Embedded CSS for the standalone-HTML writer: clean, readable, GitHub-ish.
_HTML_CSS = """
:root { color-scheme: light dark; }
html { font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }
body { max-width: 46rem; margin: 3rem auto; padding: 0 1.25rem; color: #1b1f24; }
h1, h2, h3, h4 { line-height: 1.25; margin-top: 1.8em; }
h1, h2 { border-bottom: 1px solid #d8dee4; padding-bottom: .3em; }
code { background: #f3f4f6; padding: .15em .35em; border-radius: 4px; font-size: .9em; }
pre { background: #f6f8fa; padding: 1rem; border-radius: 8px; overflow: auto; }
pre code { background: none; padding: 0; }
blockquote { color: #57606a; border-left: .25em solid #d0d7de; margin: 0; padding: 0 1em; }
table { border-collapse: collapse; }
th, td { border: 1px solid #d0d7de; padding: .4em .8em; }
img { max-width: 100%; }
a { color: #0969da; }
@media (prefers-color-scheme: dark) {
  body { color: #e6edf3; background: #0d1117; }
  code { background: #21262d; }
  pre { background: #161b22; }
  th, td, h1, h2 { border-color: #30363d; }
}
""".strip()


# ---- Output format registry --------------------------------------------------

TEXT_FORMATS: dict[str, TextFormat] = {
    f.key: f
    for f in [
        # Live preview / embeddable fragment.
        TextFormat("html", "HTML", "html5", "html", "text/html",
                   extra_args=("--mathml",)),
        # Full, self-contained, styled HTML document.
        TextFormat("html_doc", "Standalone HTML", "html5", "html", "text/html",
                   standalone=True,
                   extra_args=("--mathml", "--embed-resources",
                               "-c", "__inline_css__")),
        TextFormat("latex", "LaTeX", "latex", "tex", "application/x-tex",
                   standalone=True),
        TextFormat("rst", "reStructuredText", "rst", "rst", "text/x-rst"),
        TextFormat("gfm", "Markdown (GFM)", "gfm", "md", "text/markdown"),
        TextFormat("org", "Org-mode", "org", "org", "text/x-org"),
        TextFormat("asciidoc", "AsciiDoc", "asciidoc", "adoc", "text/plain"),
        TextFormat("plain", "Plain text", "plain", "txt", "text/plain"),
    ]
}

BINARY_FORMATS: dict[str, BinaryFormat] = {
    f.key: f
    for f in [
        BinaryFormat("pdf", "PDF", "pdf", "application/pdf",
                     extra_args=("--pdf-engine=tectonic",),
                     needs_tectonic=True),
        BinaryFormat("docx", "Word (DOCX)", "docx",
                     "application/vnd.openxmlformats-officedocument."
                     "wordprocessingml.document"),
        BinaryFormat("odt", "OpenDocument (ODT)", "odt",
                     "application/vnd.oasis.opendocument.text"),
        BinaryFormat("pptx", "PowerPoint (PPTX)", "pptx",
                     "application/vnd.openxmlformats-officedocument."
                     "presentationml.presentation"),
        BinaryFormat("epub", "EPUB", "epub", "application/epub+zip"),
    ]
}


def _require_pandoc() -> str:
    if not PANDOC:
        raise ToolMissingError(
            "pandoc is not installed or not on PATH. Install it (e.g. "
            "`brew install pandoc`) and restart the server."
        )
    return PANDOC


def _run(args: list[str], source: str, *, timeout: int) -> bytes:
    """Run a pandoc/tectonic command, feeding ``source`` on stdin."""
    try:
        proc = subprocess.run(
            args,
            input=source.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise ConversionError(
            f"Conversion timed out after {timeout}s — the document may be "
            "too large or complex."
        ) from None
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        # Keep it to the last few lines; pandoc/LaTeX logs can be enormous.
        tail = "\n".join(detail.splitlines()[-12:]) or "unknown error"
        raise ConversionError(tail)
    return proc.stdout


def to_text(source: str, key: str) -> str:
    """Convert markdown ``source`` to a text format. Returns a string."""
    fmt = TEXT_FORMATS.get(key)
    if fmt is None:
        raise ConversionError(f"Unknown text format: {key!r}")

    args = [_require_pandoc(), "-f", INPUT_FORMAT, "-t", fmt.pandoc_to]
    if fmt.standalone:
        args.append("-s")
    if key == "html_doc":
        args.append(f"--metadata=title:{_document_title(source)}")

    with tempfile.TemporaryDirectory() as tmp:
        for arg in fmt.extra_args:
            if arg == "__inline_css__":
                css_path = Path(tmp) / "markdownland.css"
                css_path.write_text(_HTML_CSS, encoding="utf-8")
                args.append(str(css_path))
            else:
                args.append(arg)

        out = _run(args, source, timeout=TEXT_TIMEOUT)
    return out.decode("utf-8", "replace")


def from_html(html: str) -> str:
    """Convert pasted rich text (HTML) into GFM markdown.

    Used when someone pastes from a web page, Word, or Google Docs: the browser
    hands us ``text/html``, and we round-trip it through pandoc so the editor
    receives clean markdown instead of raw tags. ``--wrap=none`` avoids hard
    line wrapping that would otherwise litter the source.
    """
    args = [_require_pandoc(), "-f", "html", "-t", "gfm", "--wrap=none"]
    out = _run(args, html, timeout=TEXT_TIMEOUT)
    return out.decode("utf-8", "replace").strip()


def _document_title(source: str) -> str:
    """Best-effort title for standalone exports."""
    lines = source.splitlines()
    if lines and lines[0].strip() in {"---", "+++"}:
        marker = lines[0].strip()
        for line in lines[1:]:
            if line.strip() == marker:
                break
            match = _TITLE_META.match(line)
            if match:
                title = match.group(1).strip().strip('"\'')
                if title:
                    return title

    match = _H1.search(source)
    if match:
        title = _HEADING_ID.sub("", match.group(1)).strip()
        title = re.sub(r"[`*_~]", "", title)
        if title:
            return title
    return "markdownland"


# File extension -> pandoc reader, for importing dropped non-markdown files.
# Not advertised in the UI; the drop handler falls back to this for anything
# that isn't already markdown/plain text.
IMPORT_READERS: dict[str, str] = {
    ".docx": "docx", ".odt": "odt", ".rtf": "rtf",
    ".epub": "epub", ".fb2": "fb2",
    ".pptx": "pptx", ".xlsx": "xlsx",
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".tex": "latex", ".latex": "latex", ".ltx": "latex",
    ".rst": "rst", ".org": "org", ".textile": "textile",
    ".adoc": "asciidoc", ".asciidoc": "asciidoc",
    ".ipynb": "ipynb", ".typ": "typst", ".djot": "djot",
    ".opml": "opml", ".docbook": "docbook",
    ".wiki": "mediawiki", ".mediawiki": "mediawiki",
    ".man": "man", ".muse": "muse", ".jira": "jira",
    ".csv": "csv", ".tsv": "tsv",
}


IMPORT_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "key": "markdown",
        "label": "Markdown / plain text",
        "extensions": sorted(_TEXT_EXTENSIONS),
        "requires": [],
        "tool": None,
    },
    {
        "key": "office",
        "label": "Office documents",
        "extensions": [".docx", ".odt", ".rtf", ".pptx", ".xlsx"],
        "requires": ["pandoc"],
        "tool": "pandoc",
    },
    {
        "key": "web",
        "label": "Web and ebooks",
        "extensions": [".html", ".htm", ".xhtml", ".epub", ".fb2"],
        "requires": ["pandoc"],
        "tool": "pandoc",
    },
    {
        "key": "source",
        "label": "Markup and source formats",
        "extensions": [
            ".adoc", ".asciidoc", ".csv", ".djot", ".docbook", ".ipynb",
            ".jira", ".latex", ".ltx", ".man", ".mediawiki", ".muse",
            ".opml", ".org", ".rst", ".tex", ".textile", ".tsv", ".typ",
            ".wiki",
        ],
        "requires": ["pandoc"],
        "tool": "pandoc",
    },
    {
        "key": "pdf",
        "label": "PDF",
        "extensions": [".pdf"],
        "requires": ["pdftotext"],
        "tool": "pdftotext",
    },
)


def _tool_available(tool: str | None) -> bool:
    if tool is None:
        return True
    return {
        "pandoc": bool(PANDOC),
        "tectonic": bool(TECTONIC),
        "pdftotext": bool(PDFTOTEXT),
    }.get(tool, False)


def importable_extensions() -> set[str]:
    """Extensions we can import, plus the markdown/text ones handled directly."""
    pdf = {".pdf"} if PDFTOTEXT else set()
    return set(IMPORT_READERS) | pdf | _TEXT_EXTENSIONS


def import_accept() -> str:
    """HTML file-input accept value for formats currently importable."""
    return ",".join(sorted(importable_extensions()))


def format_catalog() -> dict[str, object]:
    """JSON-friendly catalog of import/export support and tool availability."""
    tools = health()
    text = [
        {
            "key": f.key,
            "label": f.label,
            "extension": f".{f.extension}",
            "mimetype": f.mimetype,
            "standalone": f.standalone,
            "available": bool(PANDOC),
            "requires": ["pandoc"],
        }
        for f in TEXT_FORMATS.values()
    ]
    binary = [
        {
            "key": f.key,
            "label": f.label,
            "extension": f".{f.extension}",
            "mimetype": f.mimetype,
            "available": bool(PANDOC) and (not f.needs_tectonic or bool(TECTONIC)),
            "requires": ["pandoc", *(["tectonic"] if f.needs_tectonic else [])],
        }
        for f in BINARY_FORMATS.values()
    ]
    imports = [
        {
            **group,
            "available": _tool_available(group["tool"]),
        }
        for group in IMPORT_GROUPS
    ]
    return {"tools": tools, "text": text, "binary": binary, "import": imports}


def _decode_unknown_text(data: bytes, ext: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ConversionError(
            f"Don't know how to import {ext or 'this file type'}."
        ) from None

    controls = len(_CONTROL_CHARS.findall(text))
    if controls and controls / max(len(text), 1) > 0.01:
        raise ConversionError(
            f"Don't know how to import {ext or 'this file type'}."
        )
    return text


def from_pdf(data: bytes) -> str:
    """Extract a PDF's text via poppler's ``pdftotext``.

    PDF isn't a pandoc reader, so we shell out to ``pdftotext``. PDFs carry no
    markdown structure, so the result is prose, lightly tidied: page breaks
    dropped, trailing spaces trimmed, runs of blank lines collapsed.
    """
    if not PDFTOTEXT:
        raise ToolMissingError(
            "pdftotext (poppler) is not installed, so PDF import is unavailable. "
            "Install it (e.g. `brew install poppler`) and restart the server."
        )
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input.pdf"
        src.write_bytes(data)
        out = _run(
            [PDFTOTEXT, "-enc", "UTF-8", "-nopgbrk", str(src), "-"],
            "", timeout=TEXT_TIMEOUT,
        )
    text = out.decode("utf-8", "replace")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def from_file(data: bytes, filename: str) -> str:
    """Import a dropped file (pdf, docx, html, rtf, …) as GFM markdown.

    The reader is chosen from the file extension. Unknown extensions are tried
    as UTF-8 text (markdown passthrough); genuinely binary unknowns raise.
    """
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return from_pdf(data)
    reader = IMPORT_READERS.get(ext)
    if reader is None:
        return _decode_unknown_text(data, ext)

    pandoc = _require_pandoc()
    # Pandoc reads binary formats (docx/odt/epub/…) from a real file, not stdin.
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"input{ext}"
        src.write_bytes(data)
        args = [pandoc, "-f", reader, "-t", "gfm", "--wrap=none", str(src)]
        out = _run(args, "", timeout=TEXT_TIMEOUT)
    return out.decode("utf-8", "replace").strip()


def to_binary(source: str, key: str) -> bytes:
    """Convert markdown ``source`` to a binary format. Returns bytes."""
    fmt = BINARY_FORMATS.get(key)
    if fmt is None:
        raise ConversionError(f"Unknown binary format: {key!r}")
    if fmt.needs_tectonic and not TECTONIC:
        raise ToolMissingError(
            "tectonic (the LaTeX engine for PDF) is not installed. Install it "
            "(e.g. `brew install tectonic`) and restart the server."
        )

    pandoc = _require_pandoc()
    timeout = PDF_TIMEOUT if fmt.needs_tectonic else TEXT_TIMEOUT
    # Pandoc must write binary formats to a real file, not stdout.
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / f"out.{fmt.extension}"
        args = [pandoc, "-f", INPUT_FORMAT]
        if fmt.pandoc_to:
            args += ["-t", fmt.pandoc_to]
        args += [*fmt.extra_args, "-o", str(out_path)]
        _run(args, source, timeout=timeout)
        return out_path.read_bytes()


def health() -> dict[str, object]:
    """Report which tools are available and their versions, for diagnostics."""

    def version(binary: str | None) -> str | None:
        if not binary:
            return None
        # pandoc/tectonic use --version; poppler's pdftotext uses -v (stderr).
        for flag in ("--version", "-v"):
            try:
                out = subprocess.run([binary, flag], capture_output=True, timeout=10)
            except Exception:
                continue
            text = (out.stdout or out.stderr).decode("utf-8", "replace").strip()
            first = text.splitlines()[0] if text.splitlines() else ""
            if first and not any(w in first.lower() for w in ("error", "couldn't")):
                return first
        return "unknown"

    return {
        "pandoc": version(PANDOC),
        "tectonic": version(TECTONIC),
        "pdftotext": version(PDFTOTEXT),
    }
