// This renderer builds Markdown and whitelisted HTML as safe DOM nodes without copying active attributes.
"use strict";
window.AosMd = (() => {
  const node = (tag, text) => { const n = document.createElement(tag); if (text != null) n.textContent = text; return n; };
  const allowed = new Set(["details", "summary", "br", "sub", "sup", "kbd", "b", "i", "em", "strong", "code"]);
  // Scan complete tags, consuming quoted attribute values without interpreting HTML.
  const tagPattern = /<\/?[a-zA-Z][a-zA-Z0-9]*(?:\s+[^<>"']*?(?:"[^"]*"|'[^']*')?)*\s*\/?>/g;
  function tags(text) {
    const result = [], stack = [];
    // Code spans and fenced code are opaque, including HTML-looking text inside them.
    const opaque = [], code = /^\s*```[^\n]*(?:\n[\s\S]*?(?:^\s*```\s*$|$(?![\s\S])))/gm;
    let match;
    while ((match = code.exec(text))) opaque.push([match.index, code.lastIndex]);
    const spans = /(`+)([\s\S]*?)\1(?!`)/g;
    while ((match = spans.exec(text))) opaque.push([match.index, spans.lastIndex]);
    const pattern = new RegExp(tagPattern.source, "g");
    while ((match = pattern.exec(text))) {
      if (opaque.some(([a, b]) => match.index >= a && match.index < b)) continue;
      const raw = match[0], name = raw.match(/^<\/?([a-zA-Z0-9]+)/)[1].toLowerCase();
      const token = {raw, name, start: match.index, end: pattern.lastIndex, close: raw.startsWith("</")};
      result.push(token);
      if (stack.length && stack[stack.length - 1].name === "code" && !(name === "code" && token.close)) continue;
      if (!allowed.has(name)) continue;
      if (name === "br" && !token.close) { token.valid = true; continue; }
      if (token.close) {
        if (stack.length && stack[stack.length - 1].name === name) {
          const open = stack.pop(); open.pair = token; token.pair = open;
          open.valid = token.valid = true;
        } else {
          // Crossing/mismatched tags cannot become browser-repaired markup.
          stack.length = 0;
        }
      } else if (!/\/\s*>$/.test(raw)) stack.push(token);
    }
    return result;
  }
  function element(token) {
    const n = node(token.name);
    if (token.name === "details") {
      const attrs = token.raw.slice(token.raw.match(/^<[^\s/>]+/)[0].length, -1);
      const pattern = /([^\s=/>]+)(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?/g;
      let attr;
      while ((attr = pattern.exec(attrs))) if (attr[1].toLowerCase() === "open") n.setAttribute("open", "");
    }
    return n;
  }
  function inline(parent, text, blocks = new Map()) {
    const html = tags(text), byStart = new Map(html.map(t => [t.start, t]));
    const pattern = /(`+)([\s\S]*?)\1(?!`)|\*\*([^*]+)\*\*|<|\u0000[0-9]+\u0000/g;
    let start = 0, match;
    while ((match = pattern.exec(text))) {
      parent.append(document.createTextNode(text.slice(start, match.index)));
      const token = byStart.get(match.index);
      if (blocks.has(match[0])) parent.append(blocks.get(match[0]));
      else if (token) {
        if (token.valid && !token.close) {
          const n = element(token);
          if (token.pair) {
            const body = text.slice(token.end, token.pair.start);
            if (token.name === "code") n.textContent = body;
            else inline(n, body, blocks);
          }
          parent.append(n);
          pattern.lastIndex = token.pair ? token.pair.end : token.end;
        } else { parent.append(document.createTextNode(token.raw)); pattern.lastIndex = token.end; }
      } else if (match[0] === "<") parent.append(document.createTextNode("<"));
      else parent.append(node(match[1] != null ? "code" : "strong", match[1] == null ? match[3] : match[2]));
      start = pattern.lastIndex;
    }
    parent.append(document.createTextNode(text.slice(start)));
  }
  function blockTags(text) {
    const blocks = new Map();
    // NUL is replaced first so document text cannot impersonate an internal marker.
    text = text.replace(/\u0000/g, "\ufffd");
    const tokens = tags(text);
    let output = "", start = 0;
    for (const token of tokens) {
      if (/^\s*>/.test(text.slice(text.lastIndexOf("\n", token.start - 1) + 1, token.start))) continue;
      if (token.start < start || !token.valid || token.close || !["details", "summary"].includes(token.name)) continue;
      const n = element(token), body = text.slice(token.end, token.pair.start);
      if (token.name === "summary") inline(n, body);
      else n.append(render(body));
      const key = `\u0000${blocks.size}\u0000`;
      blocks.set(key, n);
      output += text.slice(start, token.start) + "\n\n" + key + "\n\n";
      start = token.pair.end;
    }
    return {text: output + text.slice(start), blocks};
  }
  const cells = line => line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
  const divider = line => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line);
  const rule = line => /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line);
  function render(value) {
    const fragment = document.createDocumentFragment();
    const prepared = blockTags(String(value || "").replace(/^<!-- summary[^\n]*-->\s*\n?/, ""));
    const lines = prepared.text.split(/\r?\n/), blocks = prepared.blocks;
    let i = 0;
    while (i < lines.length) {
      const line = lines[i], heading = line.match(/^(#{1,6})\s+(.+)$/), item = line.match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)$/);
      if (!line.trim()) { i++; continue; }
      if (blocks.has(line.trim())) { fragment.append(blocks.get(line.trim())); i++; continue; }
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
      if (heading) { const h = node(`h${heading[1].length}`); inline(h, heading[2], blocks); fragment.append(h); i++; continue; }
      if (rule(line)) { fragment.append(node("hr")); i++; continue; }
      if (i + 1 < lines.length && line.includes("|") && divider(lines[i + 1])) {
        const wrap = node("div"), table = node("table"), head = node("thead"), row = node("tr"), body = node("tbody");
        wrap.className = "md-table";
        cells(line).forEach(text => { const cell = node("th"); inline(cell, text, blocks); row.append(cell); });
        head.append(row); i += 2;
        while (i < lines.length && lines[i].trim() && lines[i].includes("|")) {
          const tr = node("tr"); cells(lines[i++]).forEach(text => { const cell = node("td"); inline(cell, text, blocks); tr.append(cell); }); body.append(tr);
        }
        table.append(head, body); wrap.append(table); fragment.append(wrap); continue;
      }
      if (item) {
        const ordered = !item[1], list = node(ordered ? "ol" : "ul");
        while (i < lines.length) {
          const next = lines[i].match(/^\s*(?:([-*+])|\d+[.)])\s+(.+)$/);
          if (!next || !next[1] !== ordered) break;
          const li = node("li"); inline(li, next[2], blocks); list.append(li); i++;
        }
        fragment.append(list); continue;
      }
      const paragraph = [line]; i++;
      while (i < lines.length && lines[i].trim() && !/^(?:\s*```|\s*>|#{1,6}\s|\s*(?:[-*+]\s|\d+[.)]\s))/.test(lines[i]) && !rule(lines[i])
             && !(i + 1 < lines.length && lines[i].includes("|") && divider(lines[i + 1]))) paragraph.push(lines[i++]);
      const p = node("p"); inline(p, paragraph.join(" "), blocks); fragment.append(p);
    }
    return fragment;
  }
  return {render};
})();
