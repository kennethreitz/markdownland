# ▦ markdownland

### Drag in a document. Get it back as anything.

**markdownland** is a local-first markdown workbench. Drop in Markdown — or a
Word doc, a PDF, an HTML page, an EPUB, or just rich text from your clipboard —
and it lands in a clean, multi-tab editor with a live preview. When you're
happy, export to **PDF** (real LaTeX), DOCX, ODT, EPUB, standalone HTML,
reStructuredText, Org-mode, AsciiDoc, and more.

A built-in **inspector** grades how publish-ready your document is and flags the
things that quietly break the moment your markdown leaves GitHub — relative
links, local images, Obsidian `[[wikilinks]]`, heading-level jumps, colliding
anchors, raw HTML.

No accounts. No uploading your drafts to someone's cloud. It runs on your
machine and shells out to the best open-source document tools there are.

Built on [Responder](https://responder.kennethreitz.org/) · served by
[Granian](https://github.com/emmett-framework/granian) · powered by
[pandoc](https://pandoc.org/) + [tectonic](https://tectonic-typesetting.github.io/)
+ [poppler](https://poppler.freedesktop.org/).

---

## Highlights

- **Drop or paste anything** — Markdown, rich text, HTML, DOCX, PDF, ODT, RTF,
  EPUB, PPTX, XLSX, LaTeX, reStructuredText, and more, all converted to markdown
  on the way in.
- **Multi-document tabs** with drafts auto-saved to your browser's local storage.
- **Live preview** with iA Writer-inspired code highlighting and **Mermaid**
  diagram rendering.
- **Inspector** — publish-readiness score, word/read-time stats, outline, and a
  validator for everything that breaks outside a wiki.
- **Export** to PDF, DOCX, ODT, EPUB, standalone HTML, LaTeX, and friends.
- **Copy as** rich text, HTML, reStructuredText, Org-mode, GFM, AsciiDoc, or
  plain text — straight to your clipboard.

## Run it

### The easy way — Docker

Every dependency — pandoc, tectonic, poppler, and mermaid-cli (with a system
Chromium) — is baked into the image; nothing touches your system:

```sh
make up             # docker compose up --build, serves on http://localhost:8000
# or, without compose:
make docker-run     # docker build + run
```

### Native (macOS)

Prefer to run it directly? You need [`uv`](https://docs.astral.sh/uv/) plus a few
command-line tools. All are one `brew install` away:

```sh
# 1. uv — Python packaging & the run command
brew install uv

# 2. The document tools markdownland shells out to
brew install pandoc tectonic poppler

# 3. (optional) mermaid-cli — renders flowcharts into PDF/DOCX exports
npm install -g @mermaid-js/mermaid-cli
```

| Tool | Powers | Needed for |
|------|--------|------------|
| **pandoc** | every format conversion | required |
| **tectonic** | Markdown → **PDF** via LaTeX | PDF *export* |
| **poppler** (`pdftotext`) | **PDF** → Markdown | PDF *import* |
| **mermaid-cli** (`mmdc`) | ` ```mermaid ` diagrams → images | flowcharts in exports |

> markdownland degrades gracefully: if `tectonic`, `poppler`, or `mmdc` is
> missing, the rest still works and the top bar shows which tools were found.
> (In the live preview, mermaid diagrams render in-browser; `mmdc` is only
> needed to bake them into exported files. The browser preview loads mermaid
> from a CDN, so it needs an internet connection.)

Then:

```sh
make            # list every command
make run        # sync deps + start the server on http://localhost:8000
make test       # run the test suite
make dev        # run with autoreload
```

Once deps are synced you can also start it directly with the installed
entrypoint — `uv run markdownland` (or just `markdownland` inside the venv).

## API surface

The Responder API docs live at `/docs/` when the server is running. The app also
exposes `/health` for detected tool versions and `/formats` for a JSON catalog
of import/export formats, including which ones are currently available on the
machine.

## Project layout

| Path | Purpose |
|------|---------|
| `markdownland/app.py` | Responder app + routes |
| `markdownland/convert.py` | pandoc / tectonic / poppler conversion engine |
| `markdownland/validators.py` | publishing-readiness checks |
| `markdownland/analyzer.py` | document stats + outline extraction |
| `markdownland/__main__.py` | Granian entry point (`markdownland` command) |
| `markdownland/templates/`, `markdownland/static/` | HTMX + vanilla-JS UI |
| `tests/` | pytest suite |

## License

Note that markdownland shells out to GPL tools (pandoc, poppler); they run as
separate processes and are not linked into the app.
