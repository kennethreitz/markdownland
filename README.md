# markdownland

Drag in markdown, rich text, HTML, DOCX, ODT, RTF, and more; edit it in a
multi-document workbench; then get it back as **anything**: PDF (via LaTeX),
standalone HTML, DOCX, ODT, EPUB, reStructuredText, Org-mode, and more. Plus a
publishing **inspector** that shows stats, outline, readiness score, and the
things that quietly break once your doc leaves GitHub.

Built on [Responder](https://responder.kennethreitz.org/), served by
[Granian](https://github.com/emmett-framework/granian), powered by
[pandoc](https://pandoc.org/) + [tectonic](https://tectonic-typesetting.github.io/).

## Quick start

```sh
make            # list available commands
make run        # sync deps + start the server on http://localhost:8000
make test       # run the test suite
```

Requires [`uv`](https://docs.astral.sh/uv/), `pandoc`, and (for PDF) `tectonic`:

```sh
brew install pandoc tectonic
```

## Features

- **Drop or paste** markdown, rich text, HTML, DOCX, ODT, RTF, EPUB, and more.
- **Multi-document tabs** with local draft persistence.
- **Live HTML preview** as you type (HTMX), with Mermaid diagram rendering.
- **Document inspector** — publish score, word/read-time stats, counts, outline.
- **Download** as Markdown, PDF, DOCX, ODT, EPUB, standalone HTML, or LaTeX source.
- **Copy as** rich text, HTML, reStructuredText, Org-mode, GFM, AsciiDoc, plain text.
- **Publishing validator** — warnings for relative links/images, missing alt
  text, broken internal anchors, raw HTML, duplicate anchors, unclosed code
  fences, heading-level jumps, and more.

## Layout

| File | Purpose |
|------|---------|
| `app.py` | Responder app + routes |
| `analyzer.py` | document stats + outline extraction |
| `convert.py` | pandoc/tectonic conversion engine |
| `validators.py` | publishing-readiness checks |
| `main.py` | Granian entry point |
| `templates/`, `static/` | HTMX UI |
| `tests/` | pytest suite |

## Docker

```sh
make docker-run   # build the image (with pandoc + tectonic) and run on :8000
```
