// This renderer turns escaped Markdown into a safe document fragment without active links or HTML.
"use strict";
window.AosMd = (() => {
  const node = (tag, text) => { const n = document.createElement(tag); if (text != null) n.textContent = text; return n; };
  function inline(parent, text) {
    const pattern = /`([^`]+)`|\*\*([^*]+)\*\*/g;
    let start = 0, match;
    while ((match = pattern.exec(text))) {
      parent.append(document.createTextNode(text.slice(start, match.index)));
      parent.append(node(match[1] != null ? "code" : "strong", match[1] == null ? match[2] : match[1]));
      start = pattern.lastIndex;
    }
    parent.append(document.createTextNode(text.slice(start)));
  }
  const cells = line => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
  const divider = line => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
  const rule = line => /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line);
  function render(value) {
    const fragment = document.createDocumentFragment();
    const lines = String(value || "").replace(/^<!-- summary[^\n]*-->\s*\n?/, "").split(/\r?\n/);
    let i = 0;
    while (i < lines.length) {
      const line = lines[i], heading = line.match(/^(#{1,6})\s+(.+)$/), item = line.match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)$/);
      if (!line.trim()) { i++; continue; }
      if (/^\s*```/.test(line)) {
        const code = []; i++;
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) code.push(lines[i++]);
        if (i < lines.length) i++;
        const pre = node("pre"); pre.append(node("code", code.join("\n"))); fragment.append(pre); continue;
      }
      if (/^\s*>/.test(line)) {
        const quote = [], block = node("blockquote");
        while (i < lines.length && /^\s*>/.test(lines[i])) quote.push(lines[i++].replace(/^\s*>\s?/, ""));
        block.append(render(quote.join("\n"))); fragment.append(block); continue;
      }
      if (heading) { const h = node(`h${heading[1].length}`); inline(h, heading[2]); fragment.append(h); i++; continue; }
      if (rule(line)) { fragment.append(node("hr")); i++; continue; }
      if (i + 1 < lines.length && line.includes("|") && divider(lines[i + 1])) {
        const wrap = node("div"), table = node("table"), head = node("thead"), row = node("tr"), body = node("tbody");
        wrap.className = "md-table";
        cells(line).forEach(text => { const cell = node("th"); inline(cell, text); row.append(cell); });
        head.append(row); i += 2;
        while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
          const tr = node("tr"); cells(lines[i++]).forEach(text => { const cell = node("td"); inline(cell, text); tr.append(cell); }); body.append(tr);
        }
        table.append(head, body); wrap.append(table); fragment.append(wrap); continue;
      }
      if (item) {
        const ordered = !item[1], list = node(ordered ? "ol" : "ul");
        while (i < lines.length) {
          const next = lines[i].match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)$/);
          if (!next || !next[1] !== ordered) break;
          const li = node("li"); inline(li, next[2]); list.append(li); i++;
        }
        fragment.append(list); continue;
      }
      const paragraph = [line]; i++;
      while (i < lines.length && lines[i].trim() && !/^(?:\s*```|\s*>|#{1,6}\s|\s*(?:[-*+]\s|\d+[.)]\s))/.test(lines[i]) && !rule(lines[i])
             && !(i + 1 < lines.length && lines[i].includes("|") && divider(lines[i + 1]))) paragraph.push(lines[i++]);
      const p = node("p"); inline(p, paragraph.join(" ")); fragment.append(p);
    }
    return fragment;
  }
  return {render};
})();
