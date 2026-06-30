# Spec: Live PDF preview

Status: **proposed** · Owner: TBD · Created: 2026-06-30

## Summary

Add an optional preview mode that shows the **actual typeset PDF** (rendered by
tectonic, the same engine used for export) instead of the HTML approximation.
Where the current "LaTeX look" preview *mimics* the PDF with CSS, this mode *is*
the PDF — pixel-identical to what the user downloads.

## Motivation

The HTML preview — even with the Latin Modern "LaTeX look" — can't match LaTeX's
line breaking, hyphenation, float placement, page breaks, math layout, or table
sizing. Users producing print documents want to see the real thing before
downloading. We already render the PDF on demand; this surfaces it live.

## Non-goals

- Replacing the HTML preview. The HTML preview stays the default (instant,
  editable feel). PDF preview is an opt-in mode.
- Editing/annotating the PDF.
- WYSIWYG editing. The editor remains markdown.

## UX

- A **preview-mode switch** in the preview pane head: `HTML | PDF` (segmented
  control). Remembered in `localStorage` (`markdownland:preview-mode`).
- In PDF mode the preview pane renders the compiled PDF. While a render is in
  flight, the previous PDF stays visible with a subtle "rendering…" indicator
  (no forced blank flashes).
- Debounce is longer than HTML preview (≈900ms vs 400ms) because a tectonic run
  costs ~0.5–3s. A manual "↻ render" affordance covers the impatient case.
- On a LaTeX/compile error, show the error panel (reuse `_error_fragment`) with
  the tail of tectonic's log instead of swapping the PDF.
- Scroll position is preserved across re-renders (see Display below).

## Architecture

### Server

New endpoint `POST /preview.pdf`:

- Body: `source` (same form parsing as `/preview`, via `_read_form`).
- Reuses `convert.to_binary(source, "pdf")` — so mermaid rendering, hard line
  breaks, and `--pdf-engine=tectonic` all come for free.
- Returns `application/pdf` (200) or a JSON error (422) with the log tail.
- **Caching**: memoize by `sha256(source)` → PDF bytes (bounded LRU, e.g. 16
  entries). Identical re-requests (e.g. toggling modes) return instantly.
- **Cancellation/coalescing**: a per-client in-flight guard so a burst of edits
  doesn't queue N tectonic processes. Latest-wins: supersede older renders.
  (Simplest first cut: rely on client-side abort + the cache; add server-side
  single-flight if load warrants.)
- **Limits**: keep the existing `PDF_TIMEOUT`; cap concurrency (a small
  semaphore) so the box isn't swamped by parallel tectonic runs.

### Client

Two viable display strategies:

1. **Native browser viewer** (recommended first cut). Fetch the PDF as a blob,
   `URL.createObjectURL`, set an `<iframe>`/`<embed>` `src`. Pros: zero JS deps,
   real PDF UI (zoom, find, print). Cons: limited control over scroll-sync;
   reloading the blob can jump to page 1.
2. **pdf.js** (richer). Render to a `<canvas>` stack we control. Pros: precise
   scroll preservation, page-level diffing, custom UI, scroll-sync with the
   editor later. Cons: ~1MB dep (vendor or CDN), more code.

Start with (1); graduate to (2) if scroll preservation / sync matters.

Flow (native):

```
on edit (debounced) ──▶ fetch POST /preview.pdf (AbortController; abort prior)
   ├─ 200 → blob → objectURL → iframe.src ; revoke previous URL
   └─ 422 → show error panel, keep last good PDF
```

Scroll preservation with the iframe: remember `#page` / scroll offset before
swap and restore via the PDF viewer fragment (`#page=N`) where supported; this
is the main reason to consider pdf.js.

## Degradation

- If `tectonic` is missing, the PDF mode switch is **disabled** with a tooltip
  (mirrors how the PDF download button is already gated). HTML preview unaffected.
- First tectonic run in a fresh environment may fetch LaTeX packages (slow,
  needs network); surface a one-time "preparing LaTeX…" hint.

## Performance notes

- Tectonic cold start dominates; warm runs are faster. The source-hash cache
  makes toggling and undo/redo cheap.
- Consider a tiny `\nonstopmode`-style fast path and reusing tectonic's package
  cache across runs (already persistent on disk).
- Mermaid renders are already cached per diagram source in `convert.py`.

## Security / resource

- Same input-size cap (`max_request_size`) and `PDF_TIMEOUT` as export.
- Tectonic runs on untrusted markdown → LaTeX. We rely on tectonic's sandboxing
  and pandoc's escaping; do **not** enable `--shell-escape`. Audit that raw
  LaTeX passthrough can't run shell (it can't, without shell-escape).

## Testing

- `to_binary` already covered. Add: `/preview.pdf` returns `%PDF-` for valid
  input; 422 + log tail for a deliberately broken construct; cache hit returns
  identical bytes; mode-switch persistence (JS, manual/Playwright later).

## Rollout / phases

1. **MVP**: `/preview.pdf` endpoint + cache; client mode switch; native iframe;
   error panel; tectonic-gating. (~½ day)
2. **Polish**: scroll preservation, manual render button, "rendering…" overlay,
   concurrency semaphore. (~½ day)
3. **pdf.js** (optional): canvas rendering, precise scroll, future editor↔PDF
   scroll-sync. (~1–2 days)

## Open questions

- Native iframe vs pdf.js for v1 — accept page-1 jump initially, or invest in
  pdf.js up front?
- Per-session vs global render cache/semaphore (matters once multi-user).
- Should PDF mode reuse the existing PDF **download** path/file to avoid double
  rendering when a user previews then downloads? (Cache makes this moot.)
