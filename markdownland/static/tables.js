// markdownland — markdown table helpers for the editor textarea.
// Smart Enter (auto separator + new rows), Tab between cells, align/format,
// and an insert-table template. Pure parsing/formatting lives up top so it can
// be unit-tested; DOM wiring is below.
(() => {
  "use strict";

  // ---- pure helpers (testable) ---------------------------------------------

  const SEP_RE = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

  function isSeparator(line) {
    return SEP_RE.test(line) && line.includes("-");
  }

  function isTableRow(line) {
    return line.includes("|") && line.trim() !== "";
  }

  function splitCells(line) {
    let s = line.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|")) s = s.slice(0, -1);
    return s.split(/(?<!\\)\|/).map((c) => c.trim());
  }

  function alignOf(cell) {
    const left = cell.startsWith(":");
    const right = cell.endsWith(":");
    if (left && right) return "center";
    if (right) return "right";
    if (left) return "left";
    return "";
  }

  // Format an array of raw table lines into aligned strings.
  function formatTable(rows) {
    const parsed = rows.map(splitCells);
    const sepIdx = rows.findIndex(isSeparator);
    const ncols = Math.max(...parsed.map((r) => r.length));
    parsed.forEach((r) => { while (r.length < ncols) r.push(""); });

    const aligns = new Array(ncols).fill("");
    if (sepIdx >= 0) parsed[sepIdx].forEach((c, i) => (aligns[i] = alignOf(c)));

    const widths = new Array(ncols).fill(3);
    parsed.forEach((r, ri) => {
      if (ri === sepIdx) return;
      r.forEach((c, i) => (widths[i] = Math.max(widths[i], c.length)));
    });

    const padCell = (text, i) => {
      const w = widths[i];
      if (aligns[i] === "right") return text.padStart(w);
      if (aligns[i] === "center") {
        const total = w - text.length;
        const left = Math.floor(total / 2);
        return " ".repeat(left) + text + " ".repeat(total - left);
      }
      return text.padEnd(w);
    };
    const sepCell = (i) => {
      const w = widths[i];
      if (aligns[i] === "center") return ":" + "-".repeat(Math.max(1, w - 2)) + ":";
      if (aligns[i] === "right") return "-".repeat(Math.max(1, w - 1)) + ":";
      if (aligns[i] === "left") return ":" + "-".repeat(Math.max(1, w - 1));
      return "-".repeat(w);
    };

    return parsed.map((r, ri) => {
      const cells = r.map((c, i) => (ri === sepIdx ? sepCell(i) : padCell(c, i)));
      return "| " + cells.join(" | ") + " |";
    });
  }

  function emptyRow(n) {
    return "| " + new Array(n).fill("").join(" | ") + " |";
  }
  function separatorRow(n) {
    return "| " + new Array(n).fill("---").join(" | ") + " |";
  }

  // Export pure helpers for tests when running under Node.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = { isSeparator, isTableRow, splitCells, formatTable,
                       emptyRow, separatorRow };
    return;
  }

  // ---- DOM wiring -----------------------------------------------------------

  const ta = document.getElementById("source");
  if (!ta) return;

  const lines = (v) => v.split("\n");

  function lineBounds(value, pos) {
    const start = value.lastIndexOf("\n", pos - 1) + 1;
    let end = value.indexOf("\n", pos);
    if (end < 0) end = value.length;
    return { start, end };
  }

  function lineIndexAt(value, pos) {
    let idx = 0;
    for (let i = 0; i < pos; i++) if (value[i] === "\n") idx++;
    return idx;
  }

  function setValue(next, caret) {
    if (window.mdReplace) return window.mdReplace(ta, next, caret); // undo-safe
    ta.value = next;
    if (caret != null) ta.setSelectionRange(caret, caret);
    ta.focus();
    ta.dispatchEvent(new Event("input", { bubbles: true })); // refresh preview
  }

  function blockRange(ls, idx) {
    let s = idx, e = idx;
    while (s > 0 && isTableRow(ls[s - 1])) s--;
    while (e < ls.length - 1 && isTableRow(ls[e + 1])) e++;
    return { s, e };
  }

  function offsetOfLine(ls, idx) {
    let off = 0;
    for (let i = 0; i < idx; i++) off += ls[i].length + 1;
    return off;
  }

  function handleEnter() {
    const v = ta.value, pos = ta.selectionStart;
    if (pos !== ta.selectionEnd) return false;
    const { start, end } = lineBounds(v, pos);
    const line = v.slice(start, end);
    if (!isTableRow(line)) return false;

    const ls = lines(v);
    const idx = lineIndexAt(v, start);
    const cells = splitCells(line);
    const n = Math.max(1, cells.length);
    const blk = blockRange(ls, idx);
    const nextLine = ls[idx + 1] || "";

    // Header row with no separator yet -> insert separator + first body row.
    if (idx === blk.s && !isSeparator(nextLine)) {
      const insert = "\n" + separatorRow(n) + "\n" + emptyRow(n);
      setValue(v.slice(0, end) + insert + v.slice(end),
        end + insert.length - emptyRow(n).length + 2);
      return true;
    }
    // Empty body row -> leave the table (clear the row, drop to a blank line).
    if (cells.every((c) => c === "")) {
      setValue(v.slice(0, start) + v.slice(end), start);
      return true;
    }
    // Normal body row -> add another row below.
    const insert = "\n" + emptyRow(n);
    setValue(v.slice(0, end) + insert + v.slice(end), end + 3);
    return true;
  }

  function handleTab(shift) {
    const v = ta.value, pos = ta.selectionStart;
    const { start, end } = lineBounds(v, pos);
    const line = v.slice(start, end);
    if (!isTableRow(line)) return false;

    const pipes = [];
    for (let i = 0; i < line.length; i++) {
      if (line[i] === "|" && line[i - 1] !== "\\") pipes.push(i);
    }
    if (pipes.length < 2) return false;
    const col = pos - start;

    if (shift) {
      let target = null;
      for (let k = pipes.length - 1; k >= 0; k--) {
        if (pipes[k] < col - 1) { target = pipes[k]; break; }
      }
      if (target == null) return true;
      const caret = Math.min(start + target + 2, end);
      ta.setSelectionRange(caret, caret);
      return true;
    }
    let target = null;
    for (const p of pipes) if (p >= col) { target = p; break; }
    if (target == null || target === pipes[pipes.length - 1]) {
      return handleEnter() || true; // past the last cell -> new row
    }
    const caret = Math.min(start + target + 2, end);
    ta.setSelectionRange(caret, caret);
    return true;
  }

  function formatCurrentTable() {
    const v = ta.value;
    const ls = lines(v);
    const idx = lineIndexAt(v, ta.selectionStart);
    const targets = isTableRow(ls[idx]) ? [blockRange(ls, idx)] : allBlocks(ls);
    if (!targets.length) return;
    // Rewrite bottom-up so earlier indices stay valid.
    for (const { s, e } of targets.sort((a, b) => b.s - a.s)) {
      ls.splice(s, e - s + 1, ...formatTable(ls.slice(s, e + 1)));
    }
    const caretLine = isTableRow(ls[idx]) ? idx : 0;
    setValue(ls.join("\n"), offsetOfLine(ls, caretLine));
  }

  function allBlocks(ls) {
    const blocks = [];
    let i = 0;
    while (i < ls.length) {
      if (isTableRow(ls[i]) && (isSeparator(ls[i + 1] || "") ||
          (isTableRow(ls[i + 1] || "") && isSeparator(ls[i + 2] || "")))) {
        const { s, e } = blockRange(ls, i);
        blocks.push({ s, e });
        i = e + 1;
      } else i++;
    }
    return blocks;
  }

  function insertTable() {
    const v = ta.value, pos = ta.selectionStart;
    const before = v.slice(0, pos);
    const after = v.slice(ta.selectionEnd);
    const lead = before === "" || before.endsWith("\n\n") ? ""
      : before.endsWith("\n") ? "\n" : "\n\n";
    const tpl = [
      "| Column A | Column B | Column C |",
      "| -------- | -------- | -------- |",
      "|          |          |          |",
    ].join("\n");
    setValue(before + lead + tpl + "\n" + after, before.length + lead.length + 2);
  }

  ta.addEventListener("keydown", (e) => {
    if (e.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
      if (handleEnter()) e.preventDefault();
    } else if (e.key === "Tab") {
      if (handleTab(e.shiftKey)) e.preventDefault();
    } else if (e.key.toLowerCase() === "t" && e.shiftKey && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      formatCurrentTable();
    }
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-table]");
    if (!btn) return;
    if (btn.dataset.table === "insert") insertTable();
    else if (btn.dataset.table === "format") formatCurrentTable();
  });
})();
