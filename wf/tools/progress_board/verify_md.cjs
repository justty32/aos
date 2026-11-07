// Verify the Markdown whitelist with an offline, text-only DOM fixture.
"use strict";
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict"), path = require("node:path");
class Node {
  constructor(tag, text = "") { this.tagName = tag; this.children = []; this.attrs = {}; this.value = text; }
  append(...nodes) { for (const n of nodes) this.children.push(...(n.tagName === "#fragment" ? n.children : [n])); }
  set textContent(v) { this.value = v; this.children = []; }
  get textContent() { return this.value + this.children.map(n => n.textContent).join(""); }
  setAttribute(k, v) { this.attrs[k] = v; }
}
const document = {createElement: tag => new Node(tag), createTextNode: s => new Node("#text", s), createDocumentFragment: () => new Node("#fragment")};
const context = {window: {}, document};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "web/md.js"), "utf8"), context);
const render = context.window.AosMd.render;
function all(n) { return [n, ...n.children.flatMap(all)]; }
function count(n, tag) { return all(n).filter(n => n.tagName === tag).length; }
function safe(n) {
  for (const item of all(n)) {
    assert(!["script", "style", "iframe", "img", "a"].includes(item.tagName));
    assert(Object.keys(item.attrs).every(k => item.tagName === "details" && k === "open"));
  }
}
const report = render(fs.readFileSync("/home/lorkhan/code/playground-ak/runs/2/close-report.md", "utf8"));
assert.equal(count(report, "details"), 6); assert.equal(count(report, "summary"), 6);
assert(!report.textContent.includes("<details>")); assert(count(report, "table") > 0); assert(count(report, "pre") > 0); safe(report);
const hostile = '<script>alert(1)</script> <img src=x onerror=alert(1)> <iframe>x</iframe> <a href="javascript:x">x</a> <style>x</style>\n<details open onclick="x()"><summary style="x">s</summary>safe</details>';
const malicious = render(hostile); safe(malicious); assert.equal(count(malicious, "details"), 1);
for (const tag of ['<script>', '<img src=x onerror=alert(1)>', '<iframe>', '<a href="javascript:x">', '<style>']) assert(malicious.textContent.includes(tag));
assert.equal(all(malicious).find(n => n.tagName === "details").attrs.open, "");
const nested = render('<details><summary>outer <kbd>K</kbd></summary>\n\n- a\n- b\n\n<details><summary>inner</summary>\n\n**bold**\n</details>\n</details>');
assert.equal(count(nested, "details"), 2); assert.equal(count(nested, "summary"), 2); assert.equal(count(nested, "li"), 2); assert.equal(count(nested, "kbd"), 1); assert.equal(count(nested, "strong"), 1);
for (const text of ['<details>unclosed', '</details>', '<b><i>x</b></i>']) { const n = render(text); assert.equal(n.textContent, text); assert.equal(count(n, "details") + count(n, "b") + count(n, "i"), 0); }
const coded = render('`<details><summary>literal</summary></details> **plain**`\n\n```html\n<details><summary>x</summary></details>\n```\n\n<code><details><summary>x</summary></details></code>');
assert.equal(count(coded, "details"), 0); assert.equal(count(coded, "summary"), 0); assert.equal(count(coded, "strong"), 0); assert.equal(count(coded, "code"), 3);
const quoted = render('<details title="a > b" open onclick="x()"><summary title=">">safe</summary>body</details>');
assert.equal(count(quoted, "details"), 1); assert.equal(quoted.textContent, "safebody"); safe(quoted);
const inline = render('a <b>b <i>c</i></b><br><sub>s</sub><sup>t</sup><em>e</em><strong>z</strong> end');
for (const tag of ['b', 'i', 'br', 'sub', 'sup', 'em', 'strong']) assert.equal(count(inline, tag), 1);
const codeExtra = render('<code><b>raw</b><details>raw</details></code>\n\n`` `<details>` ``');
assert.equal(count(codeExtra, "b"), 0); assert.equal(count(codeExtra, "details"), 0); assert.equal(count(codeExtra, "code"), 2);
const quote = render('> <details><summary>s</summary>\n> body\n> </details>');
assert.equal(count(quote, "blockquote"), 1); assert.equal(count(quote, "details"), 1);
console.log("Markdown whitelist checks passed (real report, hostile HTML, nesting, malformed tags, code, quoted attributes, inline tags).");
