// markdownland client: drag-and-drop, clipboard, and file downloads.
(() => {
  "use strict";

  const source = document.getElementById("source");
  const preview = document.getElementById("preview");
  const dropzone = document.getElementById("dropzone");
  const dropzoneMeta = document.getElementById("dropzone-meta");
  const toast = document.getElementById("toast");
  const filePicker = document.getElementById("file-picker");

  // ---- helpers --------------------------------------------------------------

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle("err", isError);
    toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { toast.hidden = true; }, 2600);
  }
  // Tabs (tabs.js) surface storage errors through this event.
  window.addEventListener("mdland:toast", (e) =>
    showToast(e.detail.message, e.detail.error));

  // The active tab's name drives nice download filenames.
  const activeName = () =>
    (window.mdland && window.mdland.activeName()) || "document";

  // Open content in the editor — a new tab when tabs are available.
  function openInEditor(name, content) {
    if (window.mdland) window.mdland.openDoc(name, content);
    else { source.value = content; refreshPreview(); }
  }

  function formBody(extra = {}) {
    const body = new URLSearchParams();
    body.set("source", source.value);
    body.set("filename", activeName());
    for (const [k, v] of Object.entries(extra)) body.set(k, v);
    return body;
  }

  // Re-render the live preview through HTMX after a programmatic edit.
  function refreshPreview() {
    if (window.htmx) window.htmx.trigger(source, "input");
  }

  async function errorText(resp) {
    try {
      const data = await resp.json();
      return data.error || `Request failed (${resp.status})`;
    } catch {
      return `Request failed (${resp.status})`;
    }
  }

  function filenameFrom(resp, fallback) {
    const cd = resp.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="?([^"]+)"?/);
    return m ? m[1] : fallback;
  }

  function saveBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function safeStem(name) {
    return (name || "document")
      .split(/[\\/]/).pop()
      .replace(/\.[^.]*$/, "")
      .replace(/[^A-Za-z0-9._-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "document";
  }

  function buttonLabel(btn) {
    const spans = [...btn.querySelectorAll("span")].filter((s) =>
      !s.classList.contains("btn-icon") && !s.classList.contains("chevron"));
    return (spans.at(-1) || btn).textContent.trim();
  }

  function setBusy(btn, busy) {
    btn.classList.toggle("busy", busy);
    btn.toggleAttribute("aria-busy", busy);
  }

  function maxScroll(el) {
    return Math.max(0, el.scrollHeight - el.clientHeight);
  }

  function clampRatio(n) {
    return Math.max(0, Math.min(1, Number.isFinite(n) ? n : 0));
  }

  function scrollRatio(el) {
    const max = maxScroll(el);
    return max ? el.scrollTop / max : 0;
  }

  function setScrollRatio(el, ratio) {
    el.scrollTop = clampRatio(ratio) * maxScroll(el);
  }

  let scrollSyncTarget = null;
  let scrollSyncFrame = 0;
  function syncScroll(from, to) {
    if (!from || !to) return;
    if (scrollSyncTarget === from) {
      scrollSyncTarget = null;
      return;
    }
    const ratio = scrollRatio(from);
    cancelAnimationFrame(scrollSyncFrame);
    scrollSyncFrame = requestAnimationFrame(() => {
      scrollSyncTarget = to;
      setScrollRatio(to, ratio);
      if (to === source) source.dispatchEvent(new Event("scroll"));
      setTimeout(() => {
        if (scrollSyncTarget === to) scrollSyncTarget = null;
      }, 80);
    });
  }

  function lineBounds(text, lineNumber) {
    const line = Math.max(1, Number(lineNumber) || 1);
    let start = 0;
    for (let i = 1; i < line; i++) {
      const next = text.indexOf("\n", start);
      if (next === -1) return [text.length, text.length];
      start = next + 1;
    }
    const end = text.indexOf("\n", start);
    return [start, end === -1 ? text.length : end];
  }

  function scrollEditorToLine(lineNumber) {
    const line = Math.max(1, Number(lineNumber) || 1);
    const [start, end] = lineBounds(source.value, line);
    const style = window.getComputedStyle(source);
    const lineHeight = Number.parseFloat(style.lineHeight) || 22;
    const targetTop = Math.max(0, (line - 1) * lineHeight - source.clientHeight * 0.35);
    source.focus({ preventScroll: true });
    source.setSelectionRange(start, end);
    source.scrollTop = targetTop;
    source.dispatchEvent(new Event("scroll"));
    source.classList.remove("line-jump");
    void source.offsetWidth; // restart the flash animation for repeated clicks
    source.classList.add("line-jump");
    clearTimeout(scrollEditorToLine._timer);
    scrollEditorToLine._timer = setTimeout(() => source.classList.remove("line-jump"), 900);
  }

  // ---- file loading ---------------------------------------------------------

  function looksLikeMarkdown(file) {
    return /\.(md|markdown|mdown|mkd|txt|text)$/i.test(file.name) ||
      file.type === "text/markdown" || file.type === "text/plain" || file.type === "";
  }

  function loadFile(file) {
    if (!file) return;
    if (looksLikeMarkdown(file)) {
      const reader = new FileReader();
      reader.onload = () => {
        openInEditor(file.name, reader.result);
        showToast(`Loaded ${file.name}`);
      };
      reader.onerror = () => showToast("Couldn't read that file.", true);
      reader.readAsText(file);
    } else {
      importFile(file); // docx, html, rtf, … -> markdown via pandoc
    }
  }

  // Import a non-markdown file by converting it server-side, then open it.
  async function importFile(file) {
    showToast(`Importing ${file.name}...`);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const resp = await fetch("/import/file", { method: "POST", body: fd });
      if (!resp.ok) throw new Error(await errorText(resp));
      const { markdown } = await resp.json();
      openInEditor(file.name, markdown);
      showToast(`Imported ${file.name}`);
    } catch (err) {
      showToast(`Couldn't import ${file.name}: ${err.message || err}`, true);
    }
  }

  filePicker.addEventListener("change", () => {
    if (filePicker.files.length) loadFile(filePicker.files[0]);
    filePicker.value = "";
  });

  document.querySelector(".editor-toolbar").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    if (btn.dataset.action === "open") filePicker.click();
    else if (btn.dataset.action === "clear") {
      source.value = "";
      source.dispatchEvent(new Event("input", { bubbles: true }));
      showToast("Cleared");
    }
  });

  // ---- rich-text paste -> markdown ------------------------------------------

  function insertAtCursor(text) {
    const start = source.selectionStart, end = source.selectionEnd;
    const next = source.value.slice(0, start) + text + source.value.slice(end);
    const caret = start + text.length;
    if (window.mdReplace) { window.mdReplace(source, next, caret); return; } // undo-safe
    source.value = next;
    source.setSelectionRange(caret, caret);
    refreshPreview();
  }

  source.addEventListener("paste", async (e) => {
    const cd = e.clipboardData;
    if (!cd) return;
    const html = cd.getData("text/html");
    if (!html || !html.trim()) return; // plain text — let the browser handle it
    e.preventDefault();
    const plain = cd.getData("text/plain");
    try {
      const body = new URLSearchParams();
      body.set("html", html);
      const resp = await fetch("/import/html", { method: "POST", body });
      if (!resp.ok) throw new Error(await errorText(resp));
      const { markdown } = await resp.json();
      insertAtCursor(markdown || plain || "");
      showToast("Pasted rich text as markdown");
    } catch {
      insertAtCursor(plain || ""); // fall back to a plain-text paste
      showToast("Pasted as plain text (conversion failed)", true);
    }
  });

  // ---- drag and drop --------------------------------------------------------

  let dragDepth = 0;
  function describeDraggedFile(e) {
    const file = e.dataTransfer && e.dataTransfer.items && e.dataTransfer.items[0];
    if (!dropzoneMeta || !file || file.kind !== "file") return;
    const name = file.getAsFile()?.name || "document";
    const mode = looksLikeMarkdown({ name, type: file.type || "" }) ? "open as text" : "convert to markdown";
    dropzoneMeta.textContent = `${name} - ${mode}`;
  }

  window.addEventListener("dragenter", (e) => {
    if (![...e.dataTransfer.types].includes("Files")) return;
    dragDepth++;
    describeDraggedFile(e);
    dropzone.hidden = false;
  });
  window.addEventListener("dragover", (e) => {
    e.preventDefault();
    describeDraggedFile(e);
  });
  window.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) {
      dropzone.hidden = true;
      if (dropzoneMeta) dropzoneMeta.textContent = "Markdown, PDF, DOCX, HTML, and more";
    }
  });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    dropzone.hidden = true;
    if (dropzoneMeta) dropzoneMeta.textContent = "Markdown, PDF, DOCX, HTML, and more";
    if (e.dataTransfer.files.length) loadFile(e.dataTransfer.files[0]);
  });

  document.addEventListener("click", (e) => {
    const jump = e.target.closest(".lint-jump[data-line]");
    if (!jump) return;
    scrollEditorToLine(jump.dataset.line);
  });

  // Keep the editor and rendered preview moving together. The two documents
  // rarely have identical heights, so this mirrors scroll progress by ratio.
  source.addEventListener("scroll", () => syncScroll(source, preview));
  preview.addEventListener("scroll", () => syncScroll(preview, source));
  document.addEventListener("htmx:afterSwap", (e) => {
    if (e.target === preview) syncScroll(source, preview);
  });

  // ---- action buttons -------------------------------------------------------

  async function doCopy(key, btn) {
    const resp = await fetch(`/text/${key}`, { method: "POST", body: formBody() });
    if (!resp.ok) { showToast(await errorText(resp), true); return; }
    const text = await resp.text();
    await navigator.clipboard.writeText(text);
    showToast(`Copied as ${buttonLabel(btn)}`);
  }

  async function doCopyRich() {
    const resp = await fetch("/text/html", { method: "POST", body: formBody() });
    if (!resp.ok) { showToast(await errorText(resp), true); return; }
    const html = await resp.text();
    try {
      const item = new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([source.value], { type: "text/plain" }),
      });
      await navigator.clipboard.write([item]);
    } catch {
      await navigator.clipboard.writeText(html); // fallback for older browsers
    }
    showToast("Copied as rich text");
  }

  async function doDownload(url, key, btn) {
    const resp = await fetch(url, { method: "POST", body: formBody({ download: "1" }) });
    if (!resp.ok) { showToast(await errorText(resp), true); return; }
    const blob = await resp.blob();
    saveBlob(blob, filenameFrom(resp, `${safeStem(activeName())}.${key}`));
    showToast(`Downloaded ${buttonLabel(btn)}`);
  }

  function doSourceDownload() {
    const blob = new Blob([source.value], { type: "text/markdown;charset=utf-8" });
    saveBlob(blob, `${safeStem(activeName())}.md`);
    showToast("Downloaded Markdown");
  }

  document.querySelector(".actionbar").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-kind]");
    if (!btn || btn.disabled) return;
    const { kind, key } = btn.dataset;
    setBusy(btn, true);
    try {
      if (kind === "copy") await doCopy(key, btn);
      else if (kind === "copy-rich") await doCopyRich();
      else if (kind === "download") await doDownload(`/download/${key}`, key, btn);
      else if (kind === "text-download") await doDownload(`/text/${key}`, key, btn);
      else if (kind === "source-download") doSourceDownload();
    } catch (err) {
      showToast(String(err.message || err), true);
    } finally {
      setBusy(btn, false);
    }
  });
})();
