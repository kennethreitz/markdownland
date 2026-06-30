// markdownland client: drag-and-drop, clipboard, and file downloads.
(() => {
  "use strict";

  const source = document.getElementById("source");
  const dropzone = document.getElementById("dropzone");
  const toast = document.getElementById("toast");
  const filenameLabel = document.getElementById("filename-label");

  // Remembered name of the last dropped/opened file (used for nice downloads).
  let currentName = "document";

  // ---- helpers --------------------------------------------------------------

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle("err", isError);
    toast.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { toast.hidden = true; }, 2600);
  }

  function formBody(extra = {}) {
    const body = new URLSearchParams();
    body.set("source", source.value);
    body.set("filename", currentName);
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

  // ---- file loading ---------------------------------------------------------

  function looksLikeMarkdown(file) {
    return /\.(md|markdown|mdown|mkd|txt|text)$/i.test(file.name) ||
      file.type === "text/markdown" || file.type === "text/plain" || file.type === "";
  }

  function loadFile(file) {
    if (!file) return;
    if (!looksLikeMarkdown(file)) {
      showToast(`Not a markdown/text file: ${file.name}`, true);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      source.value = reader.result;
      currentName = file.name;
      filenameLabel.textContent = file.name;
      refreshPreview();
      showToast(`Loaded ${file.name}`);
    };
    reader.onerror = () => showToast("Couldn't read that file.", true);
    reader.readAsText(file);
  }

  // ---- rich-text paste -> markdown ------------------------------------------

  function insertAtCursor(text) {
    const start = source.selectionStart, end = source.selectionEnd;
    source.value = source.value.slice(0, start) + text + source.value.slice(end);
    const caret = start + text.length;
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
  window.addEventListener("dragenter", (e) => {
    if (![...e.dataTransfer.types].includes("Files")) return;
    dragDepth++;
    dropzone.hidden = false;
  });
  window.addEventListener("dragover", (e) => { e.preventDefault(); });
  window.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) dropzone.hidden = true;
  });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    dropzone.hidden = true;
    if (e.dataTransfer.files.length) loadFile(e.dataTransfer.files[0]);
  });

  // ---- action buttons -------------------------------------------------------

  async function doCopy(key, btn) {
    const resp = await fetch(`/text/${key}`, { method: "POST", body: formBody() });
    if (!resp.ok) { showToast(await errorText(resp), true); return; }
    const text = await resp.text();
    await navigator.clipboard.writeText(text);
    showToast(`Copied as ${btn.textContent.trim()}`);
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
    saveBlob(blob, filenameFrom(resp, `${currentName}.${key}`));
    showToast(`Downloaded ${btn.textContent.trim()}`);
  }

  document.querySelector(".actionbar").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-kind]");
    if (!btn || btn.disabled) return;
    const { kind, key } = btn.dataset;
    btn.classList.add("busy");
    try {
      if (kind === "copy") await doCopy(key, btn);
      else if (kind === "copy-rich") await doCopyRich();
      else if (kind === "download") await doDownload(`/download/${key}`, key, btn);
      else if (kind === "text-download") await doDownload(`/text/${key}`, key, btn);
    } catch (err) {
      showToast(String(err.message || err), true);
    } finally {
      btn.classList.remove("busy");
    }
  });
})();
