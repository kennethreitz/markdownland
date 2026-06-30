# Changelog

All notable changes to **markdownland** are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project aims to follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

The initial development series — everything below is part of the upcoming
`0.1.0`.

### Added

- **Workbench** — drag-and-drop or paste markdown into a multi-document editor
  with a live HTML preview (HTMX). Tabs persist drafts to `localStorage` and
  wrap onto multiple rows when many documents are open.
- **Import anything** — rich text pasted from the clipboard (HTML → markdown),
  dropped files (DOCX, PPTX, XLSX, ODT, EPUB, RTF, HTML, LaTeX, reStructuredText,
  Org, AsciiDoc, Jupyter, …), and **PDF** via poppler's `pdftotext`.
- **Export** — PDF (LaTeX/tectonic), DOCX, ODT, PPTX, EPUB, RTF, FB2; and
  **copy-as** rich text, HTML, standalone HTML, LaTeX, reStructuredText, Org,
  GFM, AsciiDoc, Typst, MediaWiki, Textile, DocBook, and plain text.
- **Mermaid diagrams** — rendered live in the preview (mermaid.js), and baked
  into PDF/DOCX/EPUB/standalone-HTML exports as images via mermaid-cli (`mmdc`).
- **Document inspector** — publish-readiness score, word/read-time stats, and
  outline (collapsed by default, toggled from the top bar).
- **Publishing validator** — flags relative links, local images, missing alt
  text, broken anchors, Obsidian `[[wikilinks]]`, raw/dangerous HTML, duplicate
  anchors, heading-level skips, unclosed code fences, and more.
- **Editor helpers** — markdown table tools (insert, align, smart Enter/Tab),
  list continuation (bullets, numbered, task lists), and keyboard shortcuts
  (`⌘/Ctrl+B / I / U`, `⌘/Ctrl+] / [` to indent/outdent).
- **"LaTeX look" preview** — Latin Modern typography matching the exported PDF
  (toggle, on by default), plus iA Writer-inspired code highlighting.
- **Resizable** editor/preview split (drag handle, persisted, double-click to
  reset).
- **API** — OpenAPI docs at `/docs/`, a `/health` tool report, and a `/formats`
  catalog endpoint.
- **Ops** — `markdownland` console entrypoint, a Dockerfile (pandoc + tectonic +
  poppler + mermaid-cli), and a Makefile (`make` lists commands; `make run`).
- A spec for a future live PDF preview (`docs/specs/live-pdf-preview.md`).

### Changed

- Single newlines now render as real line breaks across every output format
  (pandoc `hard_line_breaks`), so poetry, lyrics, and addresses keep their
  layout.
- Restructured the codebase into a proper `markdownland` Python package.
- PDF import preserves significant whitespace (`pdftotext -layout`, then
  de-margined per page with page numbers stripped).

### Fixed

- Drag-and-drop overlay not hiding after a drop (CSS specificity over `[hidden]`).
- Crash on space-heavy form bodies that chardet mis-detected as UTF-7 (form
  bodies are now decoded as UTF-8 directly).
- `/docs/` failing with "Not Found /schema.yml" (OpenAPI schema is now served).
- "LaTeX look" scrollbar landing in the middle of the preview pane.
- Default port moved to 8000 (macOS Control Center holds 5000).
