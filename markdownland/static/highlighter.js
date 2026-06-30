// markdownland — lightweight editor syntax highlight overlay.
// Mirrors the textarea's text into a styled <div> behind it so markdown
// headings render in bold. The textarea's own text is transparent; only its
// caret/selection show, layered over this highlight. Monospace bold keeps the
// same advance width, so the caret stays aligned.
(() => {
  "use strict";

  const source = document.getElementById("source");
  const highlight = document.getElementById("highlight");
  if (!source || !highlight) return;

  const esc = (s) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  function build(text) {
    let inFence = false;
    let fenceCh = "";
    const lines = text.split("\n").map((line) => {
      const fence = line.match(/^\s*(`{3,}|~{3,})/);
      if (fence) {
        if (!inFence) { inFence = true; fenceCh = fence[1][0]; }
        else if (line.trim()[0] === fenceCh) inFence = false;
        return esc(line);
      }
      // ATX heading (not inside a fenced code block).
      if (!inFence && /^ {0,3}#{1,6}\s/.test(line)) {
        return `<span class="hl-h">${esc(line)}</span>`;
      }
      return esc(line);
    });
    // Trailing newline keeps the final line's height matching the textarea.
    return lines.join("\n") + "\n";
  }

  function syncScroll() {
    highlight.scrollTop = source.scrollTop;
    highlight.scrollLeft = source.scrollLeft;
  }

  function render() {
    highlight.innerHTML = build(source.value);
    syncScroll();
  }

  source.addEventListener("input", render);
  source.addEventListener("scroll", syncScroll);
  if (window.ResizeObserver) new ResizeObserver(syncScroll).observe(source);
  render();
})();
