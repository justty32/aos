// This script polls read-only detail endpoints and preserves filters, folds, and scroll while updating changed sections.
"use strict";
(() => {
  const board = document.getElementById("board");
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = String(text); return n; };
  if (location.protocol === "file:") {
    board.replaceChildren(el("p", "banner", "細節頁要開伺服器才看得到：python3 ~/repo/simple_tools/aos/wf/tools/progress_board/dash.py start，然後開 http://127.0.0.1:8765/detail.html")); return;
  }
  const params = new URLSearchParams(location.search), lineId = params.get("line"), filePath = params.get("file");
  const labels = {start: "開線", progress: "進度", done: "完成", blocked: "卡住", decision: "代定", handoff: "交棒", ask: "待你裁"};
  const colors = {start: "blue", progress: "blue", done: "green", blocked: "red", decision: "amber", handoff: "purple", ask: "amber"};
  const selected = new Set(Object.keys(labels)), folds = new Map(), signatures = new Map(), commitCache = new Map();
  const stamp = value => { const d = new Date(value); return value && !Number.isNaN(+d) ? d.toLocaleString("zh-TW", {hour12: false}) : "—"; };
  const svg = (tag, attrs = {}) => { const n = document.createElementNS("http://www.w3.org/2000/svg", tag); Object.entries(attrs).forEach(([key, value]) => n.setAttribute(key, value)); return n; };
  const link = (href, text, cls) => { const a = el("a", cls, text); a.setAttribute("href", href); return a; };
  const markdown = text => { const n = el("div", "summary-body"); n.append(window.AosMd.render(text)); return n; };
  const preserveScroll = work => { const x = window.scrollX, y = window.scrollY; work(); window.scrollTo(x, y); };
  const header = el("header"), top = el("div", "title-row"), title = el("h1", "", "aos 進度細節"), live = el("span", "live offline");
  header.append(link("index.html", "← 回看板")); top.append(title, live); header.append(top); board.append(header);
  let lastPoll = 0, polling = false;
  function connection() {
    const good = lastPoll > 0 && Date.now() - lastPoll <= 15000;
    live.className = `live${good ? "" : " offline"}`; live.replaceChildren(el("span", "dot"), el("span", "", good ? "即時" : "伺服器沒回應"));
  }
  function section(name, text) {
    const panel = el("section", "panel"), heading = el("div", "heading"), mark = svg("svg", {viewBox: "0 0 32 32", class: "icon", "aria-hidden": "true"});
    mark.append(svg("path", {d: "M5 24l7-9 7 4 8-12 M5 28h22", fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round"}));
    heading.append(mark, el("h2", "", text)); const body = el("div"); panel.dataset.section = name; panel.append(heading, body); board.append(panel); return body;
  }
  function fold(parent, key, text, defaultOpen = false) {
    const d = el("details"); d.dataset.key = key; d.open = folds.has(key) ? folds.get(key) : defaultOpen;
    d.append(el("summary", "", text)); d.addEventListener("toggle", () => folds.set(key, d.open)); parent.append(d); return d;
  }
  function update(host, value, render) {
    const next = JSON.stringify(value); if (signatures.get(host) === next) return;
    host.querySelectorAll("details[data-key]").forEach(d => folds.set(d.dataset.key, d.open));
    preserveScroll(() => { host.replaceChildren(); render(host, value); }); signatures.set(host, next);
  }
  async function request(path) {
    const response = await fetch(path, {cache: "no-store"});
    let value; try { value = await response.json(); } catch (_) { throw new Error(`讀取失敗（${response.status}）`); }
    if (!response.ok || value.ok === false) throw new Error(value.error || `讀取失敗（${response.status}）`);
    return value;
  }
  function timeline(events) {
    const strip = svg("svg", {viewBox: "0 0 900 50", class: "timeline detail-timeline", role: "img", "aria-label": "全部回報時間軸"});
    const end = Date.now(), begin = events.reduce((first, event) => Math.min(first, +new Date(event.ts) || end), end);
    strip.append(svg("line", {x1: 8, y1: 18, x2: 892, y2: 18, stroke: "var(--border)", "stroke-width": 2}));
    events.forEach(event => {
      const dot = svg("circle", {cx: 8 + Math.max(0, Math.min(1, (+new Date(event.ts) - begin) / Math.max(1, end - begin))) * 884, cy: 18, r: 4, fill: `var(--${colors[event.status] || "grey"})`});
      const hint = svg("title"); hint.textContent = `${stamp(event.ts)} ${labels[event.status] || event.status} ${event.text}`; dot.append(hint); strip.append(dot);
    });
    [[8, events.length ? stamp(begin) : "尚無回報", "start"], [892, "現在", "end"]].forEach(([x, text, anchor]) => { const label = svg("text", {x, y: 43, "text-anchor": anchor}); label.textContent = text; strip.append(label); }); return strip;
  }
  function eventList(parent, events) {
    const visible = events.filter(event => selected.has(event.status));
    if (!visible.length) { parent.append(el("p", "subtle", "無")); return; }
    const list = el("ul", "detail-events"); [...visible].reverse().forEach(event => {
      const item = el("li"), meta = el("div", "event-meta"); meta.append(el("time", "meta", stamp(event.ts)), el("span", `chip ${colors[event.status] || "grey"}`, labels[event.status] || event.status));
      item.append(meta, el("p", "event-text", event.text));
      if ((event.links || []).length) { const paths = el("div", "event-links"); event.links.forEach(path => paths.append(el("span", "", path))); item.append(paths); }
      list.append(item);
    }); parent.append(list);
  }
  function renderEvents(host, events) {
    host.append(timeline(events)); const chips = el("div", "chips filter-chips"), list = el("div");
    Object.entries(labels).forEach(([key, label]) => {
      const button = el("button", `chip ${colors[key]}`, label); button.type = "button"; button.setAttribute("aria-pressed", String(selected.has(key)));
      button.addEventListener("click", () => {
        if (selected.has(key)) selected.delete(key); else selected.add(key);
        button.setAttribute("aria-pressed", String(selected.has(key))); preserveScroll(() => { list.replaceChildren(); eventList(list, events); });
      }); chips.append(button);
    }); host.append(chips, list); eventList(list, events);
  }
  function renderHandoff(host, handoff) {
    if (!handoff) { host.append(el("p", "subtle", "沒有交棒檔")); return; }
    host.append(el("p", "meta", `${handoff.path}｜${stamp(handoff.mtime)}`)); const d = fold(host, "handoff", "交棒內容", true); d.append(markdown(handoff.text));
    if (handoff.truncated) d.append(el("p", "subtle", "內容過長，僅顯示前段。"));
  }
  function commitBody(host, data) {
    host.replaceChildren();
    if (data.error) { host.append(el("p", "subtle", `無法讀取：${data.error}`)); return; }
    host.append(el("p", "meta", `${data.author}｜${stamp(data.ts)}`)); const list = el("ul", "commit-files");
    (data.files || []).forEach(file => list.append(el("li", "", `${file.status} ${file.path}`))); host.append(list);
    if (data.truncated) host.append(el("p", "subtle", "檔案超過 300 個，僅顯示前 300 個。"));
  }
  function renderCommits(host, commits) {
    host.append(el("p", "", commits.length ? `共 ${commits.length} 筆，最新是 ${stamp(commits[0].ts)}。` : "目前沒有相關 commit。"));
    commits.forEach(commit => {
      const key = `${commit.repo}:${commit.hash}`, d = fold(host, `commit:${key}`, `${stamp(commit.ts)} ${commit.repo} ${commit.hash} ${commit.subject}`), body = el("div"); d.append(body);
      let shown = false;
      const load = async () => {
        if (!d.open || shown) return; shown = true; body.append(el("p", "subtle", "讀取中…"));
        if (!commitCache.has(key)) commitCache.set(key, request(`api/commit?repo=${encodeURIComponent(commit.repo)}&hash=${encodeURIComponent(commit.hash)}`).catch(error => ({error: error.message})));
        const result = await commitCache.get(key); preserveScroll(() => commitBody(body, result));
      };
      d.addEventListener("toggle", load); if (d.open) load();
    });
  }
  function elapsedBar(seconds) {
    const bar = svg("svg", {viewBox: "0 0 300 20", class: "elapsed-bar", role: "img", "aria-label": `已執行 ${Math.floor(seconds / 60)} 分鐘`});
    bar.append(svg("rect", {x: 0, y: 5, width: 300, height: 10, rx: 5, fill: "var(--border)"}), svg("rect", {x: 0, y: 5, width: 300 * Math.min(1, Math.max(0, seconds) / 3600), height: 10, rx: 5, fill: "var(--blue)"})); return bar;
  }
  function renderCodex(host, processes) {
    if (!processes.length) { host.append(el("p", "subtle", "目前沒有 codex 在跑")); return; }
    processes.forEach(proc => {
      const card = el("article", "process-card"), key = `pid:${proc.pid}`;
      card.append(el("h3", "process-goal", proc.goal || "沒有 goal"), el("p", "meta", `PID ${proc.pid}｜模型 ${proc.model || "未指定"}｜cwd ${proc.cwd || "未指定"}`), el("p", "meta", `開始 ${stamp(proc.started)}｜跑了 ${Math.floor(Math.max(0, proc.elapsed_sec) / 60)} 分鐘`), elapsedBar(proc.elapsed_sec));
      const log = fold(card, `${key}:log`, "log 最後 60 行");
      if (proc.log_file) log.append(el("p", "meta", proc.log_file));
      log.append(el("pre", "log-tail", proc.log_refused ? `無法讀取：${proc.log_refused}` : (proc.log_tail == null ? "沒有可讀的 log" : proc.log_tail)));
      fold(card, `${key}:argv`, "命令列").append(el("pre", "", JSON.stringify(proc.argv, null, 2)));
      if (proc.out_text != null) { const output = fold(card, `${key}:out`, "最後回報"); if (proc.out_file) output.append(el("p", "meta", proc.out_file)); output.append(markdown(proc.out_text)); }
      host.append(card);
    });
  }
  function renderReports(host, reports) {
    if (!reports.length) { host.append(el("p", "subtle", "目前沒有試驗場報告")); return; }
    const list = el("ul", "report-list"); reports.forEach(report => {
      const item = el("li"); item.append(link(`detail.html?file=${encodeURIComponent(report.path)}`, report.name), el("p", "meta", `${report.dir}｜${stamp(report.mtime)}`)); list.append(item);
    }); host.append(list);
  }
  function renderFile(host, data) {
    host.append(link("detail.html", "← 回細節總覽"), el("p", "file-path", data.path), el("p", "meta", stamp(data.mtime)));
    host.append(/\.md$/i.test(data.path) ? markdown(data.text) : el("pre", "file-text", data.text));
    if (data.truncated) host.append(el("p", "subtle", "內容過長，僅顯示前段。"));
  }
  const hosts = {};
  if (filePath != null) hosts.file = section("file", "檔案內容");
  else {
    if (lineId != null) { hosts.events = section("events", "時間線"); hosts.handoff = section("handoff", "交棒檔"); hosts.commits = section("commits", "相關 commit"); }
    else hosts.lines = section("lines", "各條工作線");
    hosts.codex = section("codex", "正在跑的 codex"); hosts.reports = section("reports", "試驗場報告");
  }
  function renderEli5(data) {
    const plain = data.eli5 || {}, main = plain.main || {}, detail = plain.detail || {};
    window.AosEli5.set(board, "overview", lineId != null ? (main.lines || {})[lineId] : main.summary, header.nextSibling);
    const line = (detail.lines || {})[lineId] || {};
    [[hosts.events, "timeline", line.timeline], [hosts.handoff, "handoff", line.handoff], [hosts.codex, "codex", detail.codex], [hosts.reports, "reports", detail.reports]].forEach(([host, key, text]) => {
      if (host) window.AosEli5.set(host.parentNode, key, text, host);
    });
  }
  function initialError(host, error) { if (!signatures.has(host)) host.replaceChildren(el("p", "subtle", `無法讀取：${error.message}`)); }
  async function refresh(path, host, consume) {
    try { const data = await request(path); consume(data); return true; }
    catch (error) { initialError(host, error); return false; }
  }
  async function poll() {
    if (polling) return; polling = true;
    const jobs = [];
    if (hosts.file) jobs.push(refresh(`api/file?path=${encodeURIComponent(filePath)}`, hosts.file, data => update(hosts.file, data, renderFile)));
    else {
      jobs.push(request("data/state.json").then(data => {
        renderEli5(data);
        if (hosts.lines) update(hosts.lines, data.lines || [], (host, lines) => {
          const buttons = el("nav", "buttons line-buttons"); lines.forEach(line => buttons.append(link(`detail.html?line=${encodeURIComponent(line.id)}`, line.title || line.id, "button"))); host.append(buttons);
        });
        return true;
      }).catch(error => { if (hosts.lines) initialError(hosts.lines, error); return false; }));
      if (!hosts.lines) jobs.push(refresh(`api/line?id=${encodeURIComponent(lineId)}`, hosts.events, data => {
        preserveScroll(() => { title.textContent = data.line.title || data.line.id; document.title = `${title.textContent}｜aos 進度細節`; });
        update(hosts.events, data.events || [], renderEvents); update(hosts.handoff, data.handoff, renderHandoff); update(hosts.commits, data.commits || [], renderCommits);
      }));
      jobs.push(refresh("api/codex", hosts.codex, data => update(hosts.codex, data.processes || [], renderCodex)));
      jobs.push(refresh("api/reports", hosts.reports, data => update(hosts.reports, data.reports || [], renderReports)));
    }
    try { if ((await Promise.all(jobs)).every(Boolean)) lastPoll = Date.now(); }
    finally { polling = false; connection(); }
  }
  connection(); poll(); setInterval(poll, 5000); setInterval(connection, 1000);
})();
