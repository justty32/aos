// This script safely renders progress snapshots and polls the local board when served over HTTP.
"use strict";
(() => {
  const board = document.getElementById("board"), ns = "http://www.w3.org/2000/svg";
  const labels = {start: "開線", progress: "進度", done: "完成", blocked: "卡住", decision: "代定", handoff: "交棒", ask: "待你裁", none: "尚未回報"};
  const colors = {start: "blue", progress: "blue", done: "green", blocked: "red", decision: "amber", handoff: "purple", ask: "amber", none: "grey"};
  let state = window.AOS_STATE || null, lastPoll = 0, contentSignature = null;
  const el = (tag, cls, value) => { const n = document.createElement(tag); if (cls) n.className = cls; if (value != null) n.textContent = String(value); return n; };
  const sv = (tag, attrs = {}) => { const n = document.createElementNS(ns, tag); Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); return n; };
  const hhmm = value => { const d = new Date(value); return value && !Number.isNaN(+d) ? d.toLocaleTimeString("zh-TW", {hour: "2-digit", minute: "2-digit", hour12: false}) : "—"; };
  const num = (value, digits = 0) => Number.isFinite(Number(value)) ? Number(value).toLocaleString("zh-TW", {maximumFractionDigits: digits}) : "—";
  const age = value => Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000)) || 0;
  function relative(value) {
    const s = String(value || "").trim();
    return s && !/^[a-z][a-z0-9+.-]*:/i.test(s) && !/^[/\\]/.test(s) && !/[\x00-\x20\x7f\\]/.test(s) ? s : null;
  }
  function link(value, title, blank = false) {
    const href = relative(value), n = el(href ? "a" : "span", "", title || value);
    if (href) { n.setAttribute("href", href); if (blank) { n.target = "_blank"; n.rel = "noopener"; } }
    return n;
  }
  function icon(kind) {
    const paths = {ask: "M7 15h18v13H7z M12 5h11v13H12z M15 9h5 M15 13h3 M4 15l3-5 M25 10l3 5", board: "M5 5h22v22H5z M5 12h22 M12 12v15", summary: "M8 4h16v24H8z M12 11h8 M12 16h8 M12 21h5", line: "M5 24l7-9 7 4 8-12 M23 7h4v4", machine: "M5 6h22v17H5z M11 28h10 M16 23v5", commit: "M16 5v7 M16 20v7 M12 16H5 M20 16h7"};
    const s = sv("svg", {viewBox: "0 0 32 32", class: "icon", "aria-hidden": "true"});
    s.append(sv("path", {d: paths[kind] || paths.line, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round"}));
    if (kind === "commit") s.append(sv("circle", {cx: 16, cy: 16, r: 4, fill: "none", stroke: "currentColor", "stroke-width": 2}));
    return s;
  }
  function heading(parent, title, kind, level = "h2") { const row = el("div", "heading"); row.append(icon(kind), el(level, "", title)); parent.append(row); return row; }
  function details(parent, title, key = title) { const d = el("details"); d.dataset.fold = `${parent.dataset.line || ""}:${key}`; d.append(el("summary", "", title)); parent.append(d); return d; }
  function chip(text, color) { return el("span", `chip ${color}`, text); }
  function timeline(events) {
    const s = sv("svg", {viewBox: "0 0 300 48", class: "timeline", role: "img", "aria-label": "最近二十四小時回報時間軸"});
    s.append(sv("line", {x1: 8, y1: 18, x2: 292, y2: 18, stroke: "var(--border)", "stroke-width": 2}));
    const end = Date.now(), begin = end - 86400000;
    (events || []).forEach(([ts, status]) => {
      const x = 8 + Math.max(0, Math.min(1, (new Date(ts).getTime() - begin) / 86400000)) * 284;
      const dot = sv("circle", {cx: x, cy: 18, r: 4, fill: `var(--${colors[status] || "grey"})`});
      const title = sv("title"); title.textContent = `${hhmm(ts)} ${labels[status] || status}`; dot.append(title); s.append(dot);
    });
    [[8, "二十四小時前", "start"], [292, "現在", "end"]].forEach(([x, text, anchor]) => { const t = sv("text", {x, y: 41, "text-anchor": anchor}); t.textContent = text; s.append(t); });
    return s;
  }
  function eventList(parent, events) {
    if (!events.length) { parent.append(el("p", "subtle", "無")); return; }
    const list = el("ul");
    events.forEach(event => { const item = el("li"); item.append(el("span", "meta", `${hhmm(event.ts)} ${labels[event.status] || event.status}`), el("span", "event-text", event.text));
      if ((event.links || []).length) { const links = el("div", "event-links"); event.links.forEach(path => links.append(link(path))); item.append(links); }
      list.append(item);
    }); parent.append(list);
  }
  function summaryPanel(data) {
    const box = el("section", "panel"); box.dataset.summary = "true"; heading(box, "匯總", "summary");
    const body = el("div", "summary-body"); body.append(window.AosMd.render(data.latest_md || "尚未產生匯總。")); box.append(body);
    const cost = data.cost || {}, parts = [`上次匯總 ${hhmm(data.latest_ts)}`, `今天 ${num(cost.runs_today || 0)} 次、共 ${num(cost.tokens_today || 0)} tokens、${num(cost.seconds_today || 0, 1)} 秒`, `下次最早 ${hhmm(data.next_eligible_ts)}`];
    if (!data.enabled) parts.push("匯總已關"); if (data.running) parts.push("匯總中…"); box.append(el("p", "subtle", parts.join("｜")));
    if (data.latest_file) box.append(link(`detail.html?file=${encodeURIComponent(data.latest_file)}`, "看全文"));
    const history = details(box, "歷史匯總"), list = el("ul", "history-list");
    (data.history || []).forEach(entry => { const item = el("li"); item.append(link(`detail.html?file=${encodeURIComponent(entry.file)}`, String(entry.ts || entry.file))); list.append(item); });
    history.append(list.children.length ? list : el("p", "subtle", "無")); return box;
  }
  function lineCard(line) {
    const card = el("article", "line-card"); card.dataset.line = line.id; heading(card, line.title || line.id, "line");
    const more = link(`detail.html?line=${encodeURIComponent(line.id)}`, "看細節"); more.className = "button"; card.append(more);
    const rounds = link(`rounds.html?line=${encodeURIComponent(line.id)}`, "輪次"); rounds.className = "button"; card.append(rounds);
    const chips = el("div", "chips"); chips.append(chip(labels[line.status] || line.status, colors[line.status] || "grey"));
    if (line.stale) chips.append(chip(`安靜 ${age(line.last_ts)} 分鐘`, "grey")); card.append(chips, timeline(line.timeline));
    card.append(el("p", "doing", `在做：${line.doing || "尚未回報"}`));
    if (line.blocked) card.append(el("p", "blocked", `卡住：${line.blocked.text}`));
    const decisions = details(card, "代定"), badge = el("span", "badge", (line.decisions || []).length); decisions.firstChild.append(badge); eventList(decisions, line.decisions || []);
    eventList(details(card, "最近"), line.events || []);
    if (line.handoff) { const handoff = line.handoff, d = details(card, handoff.exists ? `交棒檔 ${hhmm(handoff.mtime)} 更新` : "交棒檔尚未建立", "handoff"); d.append(el("p", "handoff", handoff.updated_line || "無更新說明"), el("p", "subtle", handoff.path)); }
    return card;
  }
  function gauge(label, ratio, value) {
    const safe = Math.max(0, Math.min(1, ratio || 0)), s = sv("svg", {viewBox: "0 0 120 88", class: "gauge", role: "img", "aria-label": `${label} ${value}`});
    s.append(sv("path", {d: "M16 56 A44 44 0 0 1 104 56", fill: "none", stroke: "var(--border)", "stroke-width": 9, "stroke-linecap": "round"}));
    s.append(sv("path", {d: "M16 56 A44 44 0 0 1 104 56", fill: "none", stroke: safe > .85 ? "var(--red)" : "var(--blue)", "stroke-width": 9, "stroke-linecap": "round", pathLength: 100, "stroke-dasharray": `${safe * 100} 100`}));
    [[50, value], [79, label]].forEach(([y, text]) => { const t = sv("text", {x: 60, y, "text-anchor": "middle"}); t.textContent = text; s.append(t); }); return s;
  }
  function sparkline(history) {
    const s = sv("svg", {viewBox: "0 0 440 100", class: "sparkline", role: "img", "aria-label": "負載與 codex 程序數走勢"}), rows = history || [];
    const max = Math.max(1, ...rows.flatMap(row => [Number(row[1]) || 0, Number(row[3]) || 0]));
    s.append(sv("line", {x1: 8, y1: 73, x2: 432, y2: 73, stroke: "var(--border)"}));
    [[1, "blue", "負載"], [3, "purple", "codex"]].forEach(([index, color, label], i) => {
      const points = rows.map((row, n) => `${8 + n / Math.max(1, rows.length - 1) * 424},${73 - (Number(row[index]) || 0) / max * 60}`).join(" ");
      s.append(sv("polyline", {points, fill: "none", stroke: `var(--${color})`, "stroke-width": 2}));
      const t = sv("text", {x: 8 + i * 80, y: 95}); t.textContent = label; t.style.fill = `var(--${color})`; s.append(t);
    }); return s;
  }
  function machinePanel(host, history) {
    const box = el("section", "panel"); heading(box, "機器", "machine");
    const visuals = el("div", "machine-visuals"), used = host.mem_total_mb ? (host.mem_total_mb - host.mem_avail_mb) / host.mem_total_mb : 0;
    visuals.append(gauge("負載／核心", host.load1 / Math.max(1, host.ncpu), `${num(host.load1, 1)}/${num(host.ncpu)}`), gauge("記憶體已用", used, `${num(used * 100)}%`), sparkline(history));
    box.append(visuals, el("p", "", `codex ${num(host.codex_procs)} 個、claude ${num(host.claude_procs)} 個；可用記憶體 ${num(host.mem_avail_mb / 1024, 1)} GB，負載 ${num(host.load1, 1)}／${num(host.load5, 1)}／${num(host.load15, 1)}。`)); return box;
  }
  function commitsPanel(commits) {
    const box = el("section", "panel"); heading(box, "程式更新", "commit");
    const first = commits[0]; box.append(el("p", "", first ? `最近 commit：${first.repo} ${hhmm(first.ts)}「${first.subject}」` : "最近沒有 commit。"));
    const d = details(box, "完整紀錄"), list = el("ul", "commit-list"); commits.forEach(commit => list.append(el("li", "", `${commit.repo} ${hhmm(commit.ts)} ${commit.hash}「${commit.subject}」`)));
    d.append(list.children.length ? list : el("p", "subtle", "無")); return box;
  }
  function connection() {
    const n = document.getElementById("connection"); if (!n) return;
    const ok = lastPoll && Date.now() - lastPoll <= 15000; n.className = `live${ok ? "" : " offline"}`; n.replaceChildren(el("span", "dot"), el("span", "", ok ? "即時" : "伺服器沒回應"));
  }
  const headerHost = el("div"), bodyHost = el("div");
  const asks = window.AOSAsks({el, heading, details, chip, link, poll});
  board.replaceChildren(headerHost, asks.panel, bodyHost);
  function renderEli5(data) {
    const main = (data && data.eli5 && data.eli5.main) || {};
    const summary = bodyHost.querySelector("[data-summary]");
    if (summary) window.AosEli5.set(summary, "summary", main.summary, summary.children[1] || null);
    bodyHost.querySelectorAll(".line-card").forEach(card => window.AosEli5.set(card, "line", (main.lines || {})[card.dataset.line], card.children[1] || null));
  }
  function publish(root, data) {
    const x = window.scrollX, y = window.scrollY;
    const folds = new Map([...bodyHost.querySelectorAll("details[data-fold]")].map(d => [d.dataset.fold, d.open]));
    headerHost.replaceChildren(root.firstChild); bodyHost.replaceChildren(...root.childNodes);
    bodyHost.querySelectorAll("details[data-fold]").forEach(d => { if (folds.has(d.dataset.fold)) d.open = folds.get(d.dataset.fold); });
    renderEli5(data); asks.update(data || {}); connection(); window.scrollTo(x, y);
  }
  function render(data) {
    const next = JSON.stringify(data, (key, value) => key === "eli5" || key === "generated_at" ? undefined : value);
    if (next === contentSignature) {
      renderEli5(data); asks.update(data || {});
      const time = headerHost.querySelector(".data-time"); if (time && data) time.textContent = `資料時間 ${data.generated_at}`;
      return;
    }
    contentSignature = next;
    const root = el("div"); const header = el("header"), top = el("div", "title-row"), title = el("div", "heading"); title.append(icon("board"), el("h1", "", "aos 進度")); top.append(title);
    if (location.protocol.startsWith("http")) { const live = el("span", "live"); live.id = "connection"; top.append(live); }
    const more = link("detail.html", "看細節"); more.className = "button"; top.append(more);
    header.append(top);
    if (!data) { header.append(el("p", "overview", "尚無快照；請依 README 產生資料。")); root.append(header); publish(root, data); return; }
    const lines = data.lines || [], host = data.host || {}, active = lines.filter(line => ["start", "progress", "handoff"].includes(line.status)).length, blocked = lines.filter(line => line.status === "blocked").length;
    header.append(el("p", "overview", `${lines.length} 條線：${active} 條在動、${blocked} 條卡住｜待你裁 ${num(data.asks_open || 0)} 題｜codex ${num(host.codex_procs)} 個｜負載 ${num(host.load1, 1)}/${num(host.ncpu)}｜可用記憶體 ${num(host.mem_avail_mb / 1024, 1)} GB`));
    const links = el("nav", "buttons"); (data.links || []).forEach(entry => { const href = location.protocol.startsWith("http") ? entry.http_href || entry.href : entry.href; if (relative(href)) { const a = link(href, entry.title); a.className = "button"; links.append(a); } });
    header.append(links, el("p", "data-time", `資料時間 ${data.generated_at}`)); root.append(header);
    if (location.protocol === "file:") root.append(el("p", "banner", `快照模式：這是 ${data.generated_at} 的快照；要即時更新請開伺服器（看 README）`));
    root.append(summaryPanel(data.summary || {})); const grid = el("section", "lines"); lines.forEach(line => grid.append(lineCard(line))); root.append(grid, machinePanel(host, data.load_history), commitsPanel(data.commits || []));
    if ((data.warnings || []).length) { const footer = el("footer"), d = details(footer, `提醒（${data.warnings.length}）`, "warnings"), list = el("ul"); data.warnings.forEach(warning => list.append(el("li", "", warning))); d.append(list); root.append(footer); }
    publish(root, data);
  }
  async function poll() {
    try { const response = await fetch(`data/state.json?t=${Date.now()}`, {cache: "no-store"}); if (!response.ok) throw new Error("Request failed"); const next = await response.json(); lastPoll = Date.now(); if (!state || next.generated_at !== state.generated_at || JSON.stringify(next.eli5) !== JSON.stringify(state.eli5) || JSON.stringify(next.asks) !== JSON.stringify(state.asks)) { state = next; render(state); } }
    catch (_) { /* The connection indicator retains the last successful poll time. */ }
    connection();
  }
  render(state);
  if (location.protocol.startsWith("http")) { poll(); setInterval(poll, 5000); setInterval(connection, 1000); }
})();
