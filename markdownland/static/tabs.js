// markdownland — multi-document tabs with localStorage-persisted drafts.
// Owns the editor textarea: switching tabs swaps its content; every edit is
// debounced-saved so drafts survive a reload. Exposes window.mdland so the
// drag/drop + import code can open dropped files as new tabs.
(() => {
  "use strict";

  const source = document.getElementById("source");
  const tabbar = document.getElementById("tabbar");
  const filenameLabel = document.getElementById("filename-label");
  if (!source || !tabbar) return;

  const KEY = "markdownland:docs:v1";
  let state = { tabs: [], activeId: null };
  let saveTimer = null;

  const uid = () =>
    "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);

  const activeTab = () => state.tabs.find((t) => t.id === state.activeId) || null;

  function uniqueName(base) {
    let name = (base || "untitled.md").trim() || "untitled.md";
    if (!/\.[A-Za-z0-9]+$/.test(name)) name += ".md";
    const taken = new Set(state.tabs.map((t) => t.name));
    if (!taken.has(name)) return name;
    const dot = name.lastIndexOf(".");
    const stem = dot > 0 ? name.slice(0, dot) : name;
    const ext = dot > 0 ? name.slice(dot) : "";
    let n = 2;
    while (taken.has(`${stem}-${n}${ext}`)) n++;
    return `${stem}-${n}${ext}`;
  }

  function persist() {
    const t = activeTab();
    if (t) t.content = source.value;
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      window.dispatchEvent(new CustomEvent("mdland:toast", {
        detail: { message: "Couldn't save draft (storage full)", error: true },
      }));
    }
  }

  function schedulePersist() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persist, 400);
  }

  function load() {
    try {
      const parsed = JSON.parse(localStorage.getItem(KEY) || "null");
      if (!parsed || !Array.isArray(parsed.tabs) || !parsed.tabs.length) return false;
      state = parsed;
      return true;
    } catch {
      return false;
    }
  }

  function refreshEditor() {
    const t = activeTab();
    source.value = t ? t.content : "";
    if (window.htmx) window.htmx.trigger(source, "input");
    else source.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function render() {
    const active = activeTab();
    if (filenameLabel) filenameLabel.textContent = active ? active.name : "document";
    tabbar.textContent = "";
    for (const t of state.tabs) {
      const tab = document.createElement("div");
      tab.className = "tab" + (t.id === state.activeId ? " active" : "");
      tab.dataset.id = t.id;
      tab.title = `${t.name} — double-click to rename`;
      const name = document.createElement("span");
      name.className = "tab-name";
      name.textContent = t.name;
      const close = document.createElement("button");
      close.type = "button";
      close.className = "tab-close";
      close.dataset.close = t.id;
      close.textContent = "×";
      close.title = "Close";
      tab.append(name, close);
      tabbar.append(tab);
    }
    const add = document.createElement("button");
    add.type = "button";
    add.className = "tab-add";
    add.dataset.add = "1";
    add.textContent = "+";
    add.title = "New document";
    tabbar.append(add);
  }

  function setActive(id) {
    if (id === state.activeId) return;
    persist();
    state.activeId = id;
    refreshEditor();
    render();
    persist();
  }

  function newTab(name, content) {
    const t = { id: uid(), name: uniqueName(name), content: content || "" };
    state.tabs.push(t);
    state.activeId = t.id;
    refreshEditor();
    render();
    persist();
    return t;
  }

  function closeTab(id) {
    const i = state.tabs.findIndex((t) => t.id === id);
    if (i < 0) return;
    const wasActive = state.activeId === id;
    state.tabs.splice(i, 1);
    if (!state.tabs.length) {
      newTab("untitled.md", "");
      return;
    }
    if (wasActive) {
      state.activeId = state.tabs[Math.max(0, i - 1)].id;
      refreshEditor();
    }
    render();
    persist();
  }

  function renameTab(id) {
    const t = state.tabs.find((x) => x.id === id);
    if (!t) return;
    const next = prompt("Rename document", t.name);
    if (next == null) return;
    const others = state.tabs.filter((x) => x.id !== id).map((x) => x.name);
    t.name = others.includes(next.trim()) ? uniqueName(next) : (next.trim() || t.name);
    render();
    persist();
  }

  tabbar.addEventListener("click", (e) => {
    const close = e.target.closest("[data-close]");
    if (close) { e.stopPropagation(); closeTab(close.dataset.close); return; }
    if (e.target.closest("[data-add]")) { newTab(); return; }
    const tab = e.target.closest(".tab");
    if (tab) setActive(tab.dataset.id);
  });
  tabbar.addEventListener("dblclick", (e) => {
    const tab = e.target.closest(".tab");
    if (tab) renameTab(tab.dataset.id);
  });

  source.addEventListener("input", schedulePersist);
  window.addEventListener("beforeunload", persist);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") persist();
  });

  // ⌘/Ctrl+N opens a new blank draft. (Some browsers reserve ⌘N for a new
  // window and won't deliver it to the page; it works where it's allowed.)
  window.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "n") {
      e.preventDefault();
      newTab();
    }
  });

  // Public API used by the drag/drop + import code.
  window.mdland = {
    openDoc: (name, content) => newTab(name, content),
    activeName: () => (activeTab() ? activeTab().name : "document"),
  };

  // Init: restore drafts, or seed the first tab from the server-rendered sample.
  if (load()) {
    if (!activeTab()) state.activeId = state.tabs[0].id;
    refreshEditor();
    render();
  } else {
    newTab("untitled.md", source.value);
  }
})();
