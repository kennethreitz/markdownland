"""Conversion engine for markdownland.

Thin, well-behaved wrappers around ``pandoc`` (and ``tectonic`` for PDF). All
conversions read the source markdown from stdin and write to stdout (text
formats) or to a temp file (binary formats), so nothing ever touches a shell.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Pandoc's extended markdown is the richest reader (tables, math, footnotes,
# definition lists, ...). ``tex_math_dollars`` lets people write $x^2$ math.
INPUT_FORMAT = "markdown+tex_math_dollars+emoji"

PANDOC = shutil.which("pandoc")
TECTONIC = shutil.which("tectonic")

# How long any single conversion may run before we give up (seconds). PDF gets
# a longer leash because tectonic may fetch LaTeX packages on first use.
TEXT_TIMEOUT = 30
PDF_TIMEOUT = 120


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
                               "--metadata=title:markdownland",
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
    for arg in fmt.extra_args:
        args.append(_HTML_CSS if arg == "__inline_css__" else arg)

    out = _run(args, source, timeout=TEXT_TIMEOUT)
    return out.decode("utf-8", "replace")


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
        try:
            out = subprocess.run(
                [binary, "--version"], capture_output=True, timeout=10
            )
            return out.stdout.decode("utf-8", "replace").splitlines()[0]
        except Exception:
            return "unknown"

    return {
        "pandoc": version(PANDOC),
        "tectonic": version(TECTONIC),
    }
