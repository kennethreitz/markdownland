// markdownland — editor keyboard shortcuts for the textarea.
//   ⌘/Ctrl + B / I / U  → wrap selection in **bold**, *italic*, <u>underline</u>
//   ⌘/Ctrl + ] / [      → indent / outdent the selected lines (2 spaces)
// (Tab / Shift-Tab inside lists & tables are handled by lists.js / tables.js.)
(() => {
  "use strict";

  const source = document.getElementById("source");
  if (!source) return;

  function commit(value, selStart, selEnd) {
    if (window.mdReplace) return window.mdReplace(source, value, selStart, selEnd); // undo-safe
    source.value = value;
    source.setSelectionRange(selStart, selEnd);
    source.dispatchEvent(new Event("input", { bubbles: true })); // refresh + persist
  }

  // Wrap (or unwrap) the selection with open/close markers.
  function wrap(open, close) {
    const v = source.value;
    const s = source.selectionStart;
    const e = source.selectionEnd;
    const sel = v.slice(s, e);

    // Toggle off when the markers are already inside the selection…
    if (sel.startsWith(open) && sel.endsWith(close) && sel.length >= open.length + close.length) {
      const inner = sel.slice(open.length, sel.length - close.length);
      commit(v.slice(0, s) + inner + v.slice(e), s, s + inner.length);
      return;
    }
    // …or just outside it.
    if (v.slice(s - open.length, s) === open && v.slice(e, e + close.length) === close) {
      commit(v.slice(0, s - open.length) + sel + v.slice(e + close.length),
        s - open.length, e - open.length);
      return;
    }
    // Otherwise wrap; with no selection, drop the cursor between the markers.
    commit(v.slice(0, s) + open + sel + close + v.slice(e), s + open.length, e + open.length);
  }

  function indent(outdent) {
    const v = source.value;
    const s = source.selectionStart;
    const e = source.selectionEnd;
    const blockStart = v.lastIndexOf("\n", s - 1) + 1;
    let blockEnd = v.indexOf("\n", e);
    if (blockEnd === -1) blockEnd = v.length;

    let firstDelta = 0;
    let total = 0;
    const lines = v.slice(blockStart, blockEnd).split("\n").map((line, i) => {
      if (outdent) {
        const lead = line.match(/^( {1,2}|\t)/);
        const cut = lead ? lead[0].length : 0;
        if (i === 0) firstDelta = -cut;
        total -= cut;
        return line.slice(cut);
      }
      if (i === 0) firstDelta = 2;
      total += 2;
      return "  " + line;
    });
    const next = v.slice(0, blockStart) + lines.join("\n") + v.slice(blockEnd);
    commit(next, Math.max(blockStart, s + firstDelta), e + total);
  }

  // Tab inserts two spaces (or indents the selection); Shift-Tab outdents.
  // Runs only if tables.js / lists.js didn't already claim the keystroke.
  source.addEventListener("keydown", (e) => {
    if (e.key !== "Tab" || e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    e.preventDefault();
    if (e.shiftKey) {
      indent(true);
    } else if (source.selectionStart !== source.selectionEnd) {
      indent(false);
    } else {
      const v = source.value, p = source.selectionStart;
      commit(v.slice(0, p) + "  " + v.slice(p), p + 2, p + 2);
    }
  });

  source.addEventListener("keydown", (e) => {
    if (!(e.metaKey || e.ctrlKey) || e.altKey || e.shiftKey) return;
    switch (e.key.toLowerCase()) {
      case "b": e.preventDefault(); wrap("**", "**"); break;
      case "i": e.preventDefault(); wrap("*", "*"); break;
      case "u": e.preventDefault(); wrap("<u>", "</u>"); break;
      case "]": e.preventDefault(); indent(false); break;  // also blocks history nav
      case "[": e.preventDefault(); indent(true); break;
    }
  });
})();
