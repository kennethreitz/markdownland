// Render ```mermaid code blocks in the live preview with mermaid.js (from CDN).
// Degrades gracefully: if mermaid can't be loaded (offline, blocked), the
// blocks simply stay as plain code.
let mermaid = null;
let loading = null;

function loadMermaid() {
  if (loading) return loading;
  loading = (async () => {
    try {
      const mod = await import(
        "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
      );
      mermaid = mod.default;
      const dark = matchMedia("(prefers-color-scheme: dark)").matches;
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: dark ? "dark" : "default",
      });
      return true;
    } catch {
      return false;
    }
  })();
  return loading;
}

async function renderAll(root) {
  // Pandoc emits ```mermaid as <pre class="mermaid"><code>…</code></pre>.
  const blocks = root.querySelectorAll("pre.mermaid");
  if (!blocks.length) return;
  if (!(await loadMermaid())) return;

  const nodes = [];
  blocks.forEach((pre) => {
    const code = pre.querySelector("code") || pre;
    const div = document.createElement("div");
    div.className = "mermaid";
    div.textContent = code.textContent; // textContent un-escapes &gt; etc.
    pre.replaceWith(div);
    nodes.push(div);
  });
  try {
    await mermaid.run({ nodes });
  } catch {
    // Parse error in a diagram — leave the (now plain) text in place.
  }
}

const preview = document.getElementById("preview");
if (preview) {
  document.body.addEventListener("htmx:afterSwap", (e) => {
    if (e.target && (e.target.id === "preview" || e.target.closest?.("#preview"))) {
      renderAll(preview);
    }
  });
  renderAll(preview); // handle any content already present on load
}
