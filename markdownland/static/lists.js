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
  // indent · marker (number or a single a–z/A–Z letter) · delimiter · spaces · content
  const OL = /^(\s*)(\d+|[a-zA-Z])([.)])(\s+)(.*)$/;

  // The marker that follows `token` in an ordered list: 2→3, a→b, A→B.
  function nextOrdered(token) {
    if (/^\d+$/.test(token)) return String(parseInt(token, 10) + 1);
    if (token === "z" || token === "Z") return token; // don't overflow the alphabet
    return String.fromCharCode(token.charCodeAt(0) + 1);
  }

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
      marker = `${indent}${nextOrdered(m[2])}${m[3]}${m[4]}`;
    } else {
      const checkbox = m[4] ? "[ ] " : ""; // new task items start unchecked
      marker = `${indent}${m[2]}${m[3]}${checkbox}`;
    }
    const insert = "\n" + marker;
    setValue(v.slice(0, pos) + insert + v.slice(pos), pos + insert.length);
    return true;
  }

  // The previous sibling list item at `indentLen` (or null). Used to renumber an
  // item that's outdented into a differently-numbered parent list.
  function siblingMarker(v, lineStart, indentLen) {
    const lines = v.slice(0, lineStart).split("\n");
    for (let i = lines.length - 2; i >= 0; i--) {
      const ln = lines[i];
      if (ln.trim() === "") return null;          // blank line ends the list
      const ind = ln.length - ln.trimStart().length;
      if (ind < indentLen) return null;           // reached the parent → first child
      if (ind > indentLen) continue;              // deeper nested → skip
      const o = OL.exec(ln);
      if (o) return { ordered: true, token: nextOrdered(o[2]), delim: o[3] };
      const u = UL.exec(ln);
      if (u) return { ordered: false, bullet: u[2] };
      return null;                                // non-list line at this level
    }
    return null;
  }

  // Rewrite a line's list marker to match a sibling's numbering/bullet.
  function applyMarker(line, sib) {
    const m = OL.exec(line) || UL.exec(line);
    if (!m) return line;
    const checkbox = m[4] && /\[/.test(m[4]) ? m[4] : ""; // preserve a task checkbox
    const lead = sib.ordered ? `${sib.token}${sib.delim}` : sib.bullet;
    return `${m[1]}${lead} ${checkbox}${m[5]}`;
  }

  function handleTab(outdent) {
    const v = source.value;
    const pos = source.selectionStart;
    const { start, end } = lineBounds(v, pos);
    const line = v.slice(start, end);
    if (!UL.test(line) && !OL.test(line)) return false; // only on list lines

    if (!outdent) {
      setValue(v.slice(0, start) + "  " + line + v.slice(end), pos + 2);
      return true;
    }

    const lead = line.match(/^( {1,2}|\t)/);
    if (!lead) return true; // already flush left; just swallow the Tab
    let next = line.slice(lead[0].length);
    const indentLen = next.length - next.trimStart().length;
    const sib = siblingMarker(v, start, indentLen);
    if (sib) next = applyMarker(next, sib); // adopt the parent list's numbering
    setValue(v.slice(0, start) + next + v.slice(end), start + next.length);
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
