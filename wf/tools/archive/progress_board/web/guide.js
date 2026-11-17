// This script fixes guide nav links for HTTP versus file snapshots and adds copy buttons to command blocks.
"use strict";
(() => {
  if (location.protocol.startsWith("http")) {
    document.querySelectorAll("a[data-http-href]").forEach(a => { a.href = a.dataset.httpHref; });
  }
  document.querySelectorAll(".cmd").forEach(box => {
    const pre = box.querySelector("pre"); if (!pre) return;
    const button = document.createElement("button");
    button.type = "button"; button.className = "copy"; button.textContent = "複製";
    button.addEventListener("click", async () => {
      const text = pre.textContent.split("\n").filter(line => !line.trimStart().startsWith("#")).join("\n").trim();
      try { await navigator.clipboard.writeText(text); button.textContent = "已複製"; }
      catch (_) {
        const range = document.createRange(); range.selectNodeContents(pre);
        const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range); button.textContent = "已選取，按 Ctrl+C";
      }
      setTimeout(() => { button.textContent = "複製"; }, 1600);
    });
    box.append(button);
  });
})();
