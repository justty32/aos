// cdp.mjs - drive headless Chrome over the DevTools protocol (node 24 has WebSocket built in); no puppeteer.
// Use: node tests/cdp.mjs <url> <outdir> <steps.mjs>   steps.mjs exports default async (page) => {...}
// page: eval(js), click(sel), type(text), key(key, mods), shot(name), wait(ms), until(js, ms), errors[]
// Chrome runs with its own new profile under outdir (never the user's profile).
// READ-ONLY GUARD: every request to the live ports 8767 / 8768 that is not GET/HEAD is failed in the browser
// (no say, mail, order, answer, board, ui-state write can reach the live tree). READONLY=1 does the same for every port.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import path from "node:path";

const [url, outdir, stepsFile] = process.argv.slice(2);
mkdirSync(outdir, { recursive: true });
const [VW, VH] = (process.env.VIEWPORT || "1600x1000").split("x").map(Number);   // VIEWPORT=1366x768 etc.
const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn("google-chrome-stable", ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${outdir}/profile`,
  "--no-first-run", "--no-default-browser-check", `--window-size=${VW},${VH}`, "--lang=zh-TW", "about:blank"], { stdio: "ignore" });
writeFileSync(path.join(outdir, "chrome.pid"), String(chrome.pid));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let tabs;
for (let i = 0; i < 50; i++) {
  try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (tabs.length) break; } catch { /* starting */ }
  await sleep(200);
}
const ws = new WebSocket(tabs.find((t) => t.type === "page").webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r));
let id = 0;
const wait = new Map();
const errors = [];
const blocked = [];
ws.addEventListener("message", (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); }
  if (m.method === "Runtime.exceptionThrown") errors.push("exception: " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
  if (m.method === "Runtime.consoleAPICalled" && (m.params.type === "error" || m.params.type === "warning"))
    errors.push(m.params.type + ": " + m.params.args.map((a) => a.value ?? a.description).join(" "));
  if (m.method === "Fetch.requestPaused") {
    const r = m.params.request; const u = new URL(r.url);
    const live = u.port === "8767" || u.port === "8768" || process.env.READONLY === "1";
    if (live && !["GET", "HEAD", "OPTIONS"].includes(r.method)) {
      blocked.push(r.method + " " + u.pathname);
      send("Fetch.failRequest", { requestId: m.params.requestId, errorReason: "BlockedByClient" });
    } else send("Fetch.continueRequest", { requestId: m.params.requestId });
    return;
  }
  if (m.method === "Log.entryAdded" && m.params.entry.level === "error") errors.push("log: " + m.params.entry.text + " " + (m.params.entry.url || ""));
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; wait.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Fetch.enable", { patterns: [{ urlPattern: "*" }] });
await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: VW, height: VH, deviceScaleFactor: 1, mobile: false });

const page = {
  errors, blocked,
  async eval(js) {
    const r = await send("Runtime.evaluate", { expression: js, awaitPromise: true, returnByValue: true });
    if (r.result?.exceptionDetails) throw new Error("eval: " + r.result.exceptionDetails.exception?.description);
    return r.result?.result?.value;
  },
  async goto(u) { await send("Page.navigate", { url: u }); await sleep(1500); },
  async click(sel) {
    const ok = await page.eval(`(()=>{const e=document.querySelector(${JSON.stringify(sel)}); if(!e) return false; e.scrollIntoView({block:"center"}); const r=e.getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2];})()`);
    if (!ok) throw new Error("no element " + sel);
    const [x, y] = ok;
    for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
    await sleep(250);
  },
  async dbl(sel) {
    const [x, y] = await page.eval(`(()=>{const r=document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect(); return [r.x+r.width/2,r.y+r.height/2];})()`);
    for (const c of [1, 2]) for (const type of ["mousePressed", "mouseReleased"]) await send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: c });
    await sleep(300);
  },
  async clickText(text, scope = "button") {
    const sel = await page.eval(`(()=>{const e=[...document.querySelectorAll(${JSON.stringify(scope)})].find(b=>b.textContent.includes(${JSON.stringify(text)})); if(!e) return null; e.setAttribute("data-t","x"+Math.random().toString(36).slice(2)); return '[data-t="'+e.getAttribute("data-t")+'"]';})()`);
    if (!sel) throw new Error("no " + scope + " with text " + text);
    await page.click(sel);
  },
  async type(text) { await send("Input.insertText", { text }); await sleep(150); },
  async key(key, mods = 0, code) {
    const k = { Enter: [13, "Enter"], Escape: [27, "Escape"], Backspace: [8, "Backspace"], ArrowDown: [40, "ArrowDown"], ArrowUp: [38, "ArrowUp"], ArrowRight: [39, "ArrowRight"], ArrowLeft: [37, "ArrowLeft"] }[key];
    const vk = k ? k[0] : key.toUpperCase().charCodeAt(0);
    const base = { key, code: code || (k ? k[1] : (/^[0-9]$/.test(key) ? "Digit" + key : "Key" + key.toUpperCase())), windowsVirtualKeyCode: vk, modifiers: mods };
    await send("Input.dispatchKeyEvent", { type: "keyDown", ...base, text: !k && !mods ? key : undefined });
    await send("Input.dispatchKeyEvent", { type: "keyUp", ...base });
    await sleep(200);
  },
  async shot(name) {
    const r = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(path.join(outdir, name + ".png"), Buffer.from(r.result.data, "base64"));
  },
  wait: sleep,
  async until(js, ms = 8000) {
    for (let t = 0; t < ms; t += 200) { if (await page.eval(js)) return true; await sleep(200); }
    throw new Error("timeout waiting for " + js);
  },
};

let code = 0;
try {
  await page.goto(url);
  const steps = (await import(pathToFileURL(path.resolve(stepsFile)).href)).default;
  await steps(page);
} catch (e) {
  console.log("FAIL", e.message);
  try { await page.shot("fail"); } catch { /* ignore */ }
  code = 1;
}
if (blocked.length) console.log("read-only guard blocked:", blocked.join(", "));
console.log("console errors:", errors.length ? "\n  " + errors.join("\n  ") : "none");
ws.close();
chrome.kill();
process.exit(code);
