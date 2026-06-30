// markdownland — list continuation helpers for the editor textarea.
// Enter continues a bullet/numbered/task list with the next marker; Enter on an
// empty item ends the list; Tab / Shift-Tab indent/outdent the item. Runs after
// tables.js and bows out if that handler already claimed the keystroke.
(() => {
  "use strict";

  const source = document.getElementById("source");
  if (!source) return;

  // indent · bullet · spaces · optional task checkbox · content
  const UL = /^(\s*)([-*+])(\s+)(\[[ xX]\]\s+)?(.*)$/;
  // indent · number · delimiter (. or )) · spaces · content
  const OL = /^(\s*)(\d+)([.)])(\s+)(.*)$/;

  function lineBounds(value, pos) {
    const start = value.lastIndexOf("\n", pos - 1) + 1;
    let end = value.indexOf("\n", pos);
    if (end < 0) end = value.length;
    return { start, end };
  }

  function setValue(next, caret) {
    source.value = next;
    source.setSelectionRange(caret, caret);
    source.dispatchEvent(new Event("input", { bubbles: true })); // refresh + persist
  }

  function handleEnter() {
    if (source.selectionStart !== source.selectionEnd) return false;
    const v = source.value;
    const pos = source.selectionStart;
    const { start, end } = lineBounds(v, pos);
    const line = v.slice(start, end);

    let m = UL.exec(line);
    const ordered = !m && (m = OL.exec(line));
    if (!m) return false;

    const indent = m[1];
    const content = m[5];

    // Empty item -> end the list: clear the marker, leave a blank line.
    if (content.trim() === "") {
      setValue(v.slice(0, start) + v.slice(end), start);
      return true;
    }

    // Otherwise start the next item (splitting at the cursor).
    let marker;
    if (ordered) {
      marker = `${indent}${parseInt(m[2], 10) + 1}${m[3]}${m[4]}`;
    } else {
      const checkbox = m[4] ? "[ ] " : ""; // new task items start unchecked
      marker = `${indent}${m[2]}${m[3]}${checkbox}`;
    }
    const insert = "\n" + marker;
    setValue(v.slice(0, pos) + insert + v.slice(pos), pos + insert.length);
    return true;
  }

  function handleTab(outdent) {
    const v = source.value;
    const pos = source.selectionStart;
    const { start, end } = lineBounds(v, pos);
    const line = v.slice(start, end);
    if (!UL.test(line) && !OL.test(line)) return false; // only on list lines

    if (outdent) {
      const lead = line.match(/^( {1,2}|\t)/);
      if (!lead) return true; // already flush left; just swallow the Tab
      const cut = lead[0].length;
      setValue(v.slice(0, start) + line.slice(cut) + v.slice(end),
        Math.max(start, pos - cut));
    } else {
      setValue(v.slice(0, start) + "  " + line + v.slice(end), pos + 2);
    }
    return true;
  }

  source.addEventListener("keydown", (e) => {
    if (e.defaultPrevented || e.isComposing) return; // tables.js may have claimed it
    if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
      if (handleEnter()) e.preventDefault();
    } else if (e.key === "Tab") {
      if (handleTab(e.shiftKey)) e.preventDefault();
    }
  });
})();
