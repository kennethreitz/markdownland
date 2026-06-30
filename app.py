"""markdownland — drag in a markdown file, get it back as anything.

A small Responder app that wraps pandoc (+ tectonic for PDF) behind a
drag-and-drop / paste UI. Markdown is read client-side and posted as text, so
the server only ever deals with a ``source`` string.
"""

from __future__ import annotations

import os
import re
from html import escape
from urllib.parse import parse_qs

import responder

import analyzer
import convert
import validators

api = responder.API(
    title="markdownland",
    version="0.1.0",
    description="Convert markdown to anything, via pandoc.",
    docs_route="/docs/",
    secret_key=os.environ.get("RESPONDER_SECRET_KEY", "markdownland-dev"),
    # Markdown is text; 8 MiB is a generous ceiling for a single document.
    max_request_size=8 * 1024 * 1024,
)

# Sample shown on first load so the page is never empty.
SAMPLE = """\
# Hello, markdownland 👋

Drag a `.md` file anywhere on this page — or just start typing here.

## What you get

- **PDF** rendered through LaTeX (tectonic)
- **Standalone HTML**, DOCX, ODT, EPUB, and more
- Copy as *rich text*, reStructuredText, Org-mode, …

> Math works too: $e^{i\\pi} + 1 = 0$

```python
def hello():
    return "markdownland"
```

| Format | Engine |
|--------|--------|
| PDF    | pandoc + tectonic |
| HTML   | pandoc |
"""

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


async def _read_form(req) -> dict[str, str]:
    """Parse a form body as UTF-8, bypassing Responder's chardet path.

    Responder decodes ``application/x-www-form-urlencoded`` bodies via chardet,
    which mis-detects space-heavy markdown (spaces become ``+``) as UTF-7 and
    crashes. We decode the raw body as UTF-8 ourselves; multipart bodies (which
    Responder already handles as UTF-8) are delegated unchanged.
    """
    ctype = (req.mimetype or "").lower()
    if "multipart/form-data" in ctype:
        return dict(await req.media("form"))
    raw = await req.content
    parsed = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def _form_source(data) -> str:
    """Pull the markdown ``source`` field out of a parsed form body."""
    value = data.get("source", "") if data else ""
    # Starlette form values are str; be defensive about bytes/UploadFile too.
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, str) else ""


def _download_name(data, extension: str) -> str:
    """Build a safe download filename, preserving the dropped file's stem."""
    raw = (data.get("filename") or "document") if data else "document"
    stem = _FILENAME_SAFE.sub("-", str(raw).rsplit(".", 1)[0]).strip("-")
    return f"{stem or 'document'}.{extension}"


@api.route("/")
async def index(req, resp):
    resp.html = api.template(
        "index.html",
        sample=SAMPLE,
        text_formats=convert.TEXT_FORMATS.values(),
        binary_formats=convert.BINARY_FORMATS.values(),
        tools=convert.health(),
    )


@api.route("/import/html")
async def import_html(req, resp):
    """Convert pasted rich text (HTML) to markdown for the editor."""
    data = await _read_form(req)
    html = data.get("html", "")
    if not html.strip():
        resp.media = {"markdown": ""}
        return
    try:
        resp.media = {"markdown": convert.from_html(html)}
    except convert.ConversionError as exc:
        resp.status_code = api.status_codes.HTTP_422
        resp.media = {"error": str(exc)}


@api.route("/import/file")
async def import_file(req, resp):
    """Import a dropped non-markdown file (docx, html, rtf, …) as markdown."""
    files = await req.media("files")
    upload = next(iter(files.values()), None) if files else None
    if upload is None:
        resp.status_code = 400
        resp.media = {"error": "No file uploaded."}
        return
    raw = await upload.read()
    name = getattr(upload, "filename", "") or "document"
    try:
        markdown = convert.from_file(raw, name)
    except convert.ConversionError as exc:
        resp.status_code = api.status_codes.HTTP_422
        resp.media = {"error": str(exc)}
        return
    resp.media = {"markdown": markdown, "filename": name}


@api.route("/preview")
async def preview(req, resp):
    """Live HTML preview + validation, returned as HTMX fragments.

    The rendered HTML swaps into ``#preview``; the validation panel rides along
    as an out-of-band swap into ``#lint`` so a single request updates both.
    """
    data = await _read_form(req)
    source = _form_source(data)
    report = validators.validate(source)
    analysis = analyzer.analyze(source)

    if not source.strip():
        body = '<p class="empty">Nothing to preview yet.</p>'
    else:
        try:
            body = convert.to_text(source, "html")
        except convert.ConversionError as exc:
            resp.status_code = api.status_codes.HTTP_422
            body = _error_fragment(exc)

    resp.html = body + _inspector_fragment(analysis, report) + _lint_fragment(report)


@api.route("/text/{key}")
async def text(req, resp, *, key):
    """Return a converted text format as raw text (for copy + download)."""
    data = await _read_form(req)
    source = _form_source(data)
    fmt = convert.TEXT_FORMATS.get(key)
    if fmt is None:
        resp.status_code = api.status_codes.HTTP_404
        resp.media = {"error": f"Unknown format: {key}"}
        return
    try:
        body = convert.to_text(source, key)
    except convert.ConversionError as exc:
        resp.status_code = api.status_codes.HTTP_422
        resp.media = {"error": str(exc)}
        return

    resp.content = body.encode("utf-8")
    resp.mimetype = f"{fmt.mimetype}; charset=utf-8"
    if _wants_download(data):
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="{_download_name(data, fmt.extension)}"'
        )


@api.route("/download/{key}")
async def download(req, resp, *, key):
    """Return a binary format (PDF, DOCX, …) as a file attachment."""
    data = await _read_form(req)
    source = _form_source(data)
    fmt = convert.BINARY_FORMATS.get(key)
    if fmt is None:
        resp.status_code = api.status_codes.HTTP_404
        resp.media = {"error": f"Unknown format: {key}"}
        return
    if not source.strip():
        resp.status_code = api.status_codes.HTTP_422
        resp.media = {"error": "Nothing to convert."}
        return
    try:
        resp.content = convert.to_binary(source, key)
    except convert.ConversionError as exc:
        resp.status_code = api.status_codes.HTTP_422
        resp.media = {"error": str(exc)}
        return

    resp.mimetype = fmt.mimetype
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="{_download_name(data, fmt.extension)}"'
    )


@api.route("/validate")
async def validate(req, resp):
    """Validation findings as JSON (the UI uses the /preview OOB panel)."""
    data = await _read_form(req)
    report = validators.validate(_form_source(data))
    resp.media = {
        "ok": report.ok,
        "counts": report.counts,
        "findings": [
            {
                "line": f.line, "severity": f.severity,
                "rule": f.rule, "message": f.message, "snippet": f.snippet,
            }
            for f in report.findings
        ],
    }


@api.route("/analyze")
async def analyze(req, resp):
    """Document intelligence as JSON: stats, outline, and publish score."""
    data = await _read_form(req)
    source = _form_source(data)
    report = validators.validate(source)
    resp.media = _analysis_payload(analyzer.analyze(source), report)


@api.route("/health")
async def health(req, resp):
    resp.media = {"status": "ok", "tools": convert.health()}


def _wants_download(data) -> bool:
    return bool(data and str(data.get("download", "")).lower() in {"1", "true", "yes"})


def _error_fragment(exc: Exception) -> str:
    return (
        '<div class="error"><strong>Conversion failed.</strong>'
        f"<pre>{escape(str(exc))}</pre></div>"
    )


_SEVERITY_LABEL = {"error": "Error", "warning": "Warning", "info": "Info"}


def _analysis_payload(analysis: analyzer.DocumentAnalysis, report: validators.Report) -> dict:
    score = _publish_score(report)
    return {
        **analysis.as_dict(),
        "score": {"value": score, "label": _score_label(score)},
        "validation": {"ok": report.ok, "counts": report.counts},
    }


def _publish_score(report: validators.Report) -> int:
    counts = report.counts
    return max(0, 100 - counts["error"] * 30 - counts["warning"] * 10 - counts["info"] * 2)


def _score_label(score: int) -> str:
    if score >= 90:
        return "Ready"
    if score >= 70:
        return "Review"
    return "Needs work"


def _score_class(score: int) -> str:
    if score >= 90:
        return "good"
    if score >= 70:
        return "review"
    return "bad"


def _inspector_fragment(
    analysis: analyzer.DocumentAnalysis,
    report: validators.Report,
) -> str:
    """Render stats and outline as an HTMX out-of-band swap into #inspector."""
    stats = analysis.stats
    score = _publish_score(report)
    stat_rows = [
        ("Words", f"{stats.words:,}"),
        ("Read", f"{stats.reading_minutes} min" if stats.reading_minutes else "0 min"),
        ("Headings", str(stats.headings)),
        ("Links", str(stats.links)),
        ("Images", str(stats.images)),
        ("Code", str(stats.code_blocks)),
        ("Tables", str(stats.tables)),
        ("Lines", str(stats.lines)),
    ]
    stats_html = "".join(
        f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
        for label, value in stat_rows
    )
    if analysis.outline:
        outline = "".join(
            '<li class="outline-item">'
            f'<span class="outline-level">H{heading.level}</span>'
            f'<span class="outline-title level-{heading.level}">{escape(heading.title)}</span>'
            f'<span class="outline-line">L{heading.line}</span>'
            "</li>"
            for heading in analysis.outline
        )
        outline_html = f'<ol class="outline-list">{outline}</ol>'
    else:
        outline_html = '<p class="empty tight">No headings yet.</p>'

    return (
        '<div id="inspector" hx-swap-oob="true" class="inspector">'
        '<div class="score-row">'
        f'<div class="score {_score_class(score)}"><strong>{score}</strong>'
        f'<span>{_score_label(score)}</span></div>'
        f'<div class="doc-title">{escape(analysis.title)}</div>'
        '</div>'
        f'<div class="stats-grid">{stats_html}</div>'
        '<div class="outline-head">Outline</div>'
        f'{outline_html}</div>'
    )


def _lint_fragment(report: validators.Report) -> str:
    """Render the validation panel as an HTMX out-of-band swap into #lint."""
    counts = report.counts
    if not report.findings:
        summary = '<span class="lint-clean">✓ No issues found</span>'
        items = ""
    else:
        chips = []
        for sev in ("error", "warning", "info"):
            if counts[sev]:
                chips.append(
                    f'<span class="lint-chip {sev}">{counts[sev]} '
                    f'{_SEVERITY_LABEL[sev].lower()}'
                    f'{"s" if counts[sev] != 1 else ""}</span>'
                )
        summary = "".join(chips)
        rows = []
        for f in report.findings:
            snippet = (
                f'<code class="lint-snippet">{escape(f.snippet)}</code>'
                if f.snippet else ""
            )
            rows.append(
                f'<li class="lint-item {f.severity}">'
                f'<span class="lint-line">L{f.line}</span>'
                f'<span class="lint-dot {f.severity}" title="{f.severity}"></span>'
                f'<span class="lint-msg">{escape(f.message)}{snippet}</span>'
                f"</li>"
            )
        items = f'<ul class="lint-list">{"".join(rows)}</ul>'

    return (
        '<div id="lint" hx-swap-oob="true" class="lint">'
        f'<div class="lint-summary">{summary}</div>{items}</div>'
    )
