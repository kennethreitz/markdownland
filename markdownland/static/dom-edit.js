// markdownland — undo-preserving textarea edits.
// Setting `textarea.value` directly wipes the browser's native undo history, so
// Cmd/Ctrl+Z can't reverse our table/list/format operations. document.exec-
// Command("insertText") keeps edits on the undo stack. We diff old vs new and
// only replace the changed span, so undo steps stay small and it's efficient.
(function () {
  "use strict";

  function mdReplace(ta, next, selStart, selEnd) {
    const prev = ta.value;
    if (prev !== next) {
      const min = Math.min(prev.length, next.length);
      let s = 0;
      while (s < min && prev.charCodeAt(s) === next.charCodeAt(s)) s++;
      let e = 0;
      while (
        e < min - s &&
        prev.charCodeAt(prev.length - 1 - e) === next.charCodeAt(next.length - 1 - e)
      ) e++;
      const insert = next.slice(s, next.length - e);
      ta.focus();
      ta.setSelectionRange(s, prev.length - e);
      let ok = false;
      try {
        ok = document.execCommand("insertText", false, insert);
      } catch (_) {
        ok = false;
      }
      if (!ok || ta.value !== next) ta.value = next; // fallback (loses undo)
    }
    if (selStart != null) {
      ta.setSelectionRange(selStart, selEnd == null ? selStart : selEnd);
    }
    ta.dispatchEvent(new Event("input", { bubbles: true })); // refresh + persist
  }

  window.mdReplace = mdReplace;
})();
