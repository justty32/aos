// This script renders live round reports while preserving unchanged sections, folds, hashes, and scroll.
"use strict";
(() => {
  const byId = id => document.getElementById(id), host = byId("rounds"), offline = location.protocol === "file:";
  const lineId = new URLSearchParams(location.search).get("line"), folds = new Map(), signatures = new Map();
  const labels = {start: "開始", progress: "進度", done: "完成", blocked: "卡住", decision: "代定", handoff: "交棒", ask: "待你裁", none: "尚無回報"};
  let lastPoll = 0, polling = false, firstRender = true;
  const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text != null) node.textContent = String(text); return node; };
  const sv = (tag, attrs = {}, text) => { const n = document.createElementNS("http://www.w3.org/2000/svg", tag); Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v)); if (text != null) n.textContent = text; return n; };
  const time = value => { const d = new Date(value); return value && !Number.isNaN(+d) ? d.toLocaleTimeString("zh-TW", {hour: "2-digit", minute: "2-digit", hour12: false}) : "—"; };
  const stamp = value => { const d = new Date(value); return value && !Number.isNaN(+d) ? d.toLocaleString("zh-TW", {hour12: false}) : "—"; };
  const cut = (value, max) => { const chars = [...String(value || "")]; return chars.length > max ? chars.slice(0, max).join("") + "…" : chars.join(""); };
  const link = (url, text, cls) => { const a = el("a", cls, text); a.setAttribute("href", url); return a; };
  const safeReport = value => typeof value === "string" && value.length > 0 && !/^(?:[a-z][a-z0-9+.-]*:|\/\/|\\)/i.test(value) && !/[\x00-\x20\x7f\\]/.test(value);
  function update(node, value, render) {
    const signature = JSON.stringify(value); if (signatures.get(node) === signature) return;
    node.querySelectorAll("details[data-key]").forEach(d => folds.set(d.dataset.key, d.open));
    node.replaceChildren(); render(node, value); signatures.set(node, signature);
  }
  function fold(parent, index, key, title, render) {
    const d = el("details", "fold"), body = el("div", "fold-body"); d.dataset.key = `${index}:${key}`; d.id = `round-${index}-${key}`;
    d.open = folds.get(d.dataset.key) || false; d.addEventListener("toggle", () => folds.set(d.dataset.key, d.open));
    d.append(el("summary", "", title), body); render(body); parent.append(d);
  }
  function revealHash(scroll = false) {
    let id; try { id = decodeURIComponent(location.hash.slice(1)); } catch (_) { return; }
    const target = byId(id); if (!target) return;
    for (let node = target; node; node = node.parentElement) if (node.tagName === "DETAILS") node.open = true;
    if (scroll) target.scrollIntoView();
  }
  function connection() {
    const good = lastPoll && Date.now() - lastPoll <= 15000;
    byId("connection").className = offline ? "snapshot" : "";
    byId("connection").textContent = offline ? "快照模式：顯示產生時的資料；即時更新請開伺服器。" : good ? "即時・每 5 秒更新" : "伺服器沒回應";
    const live = byId("round-live"); if (live) live.textContent = offline ? "離線快照" : good ? "即時" : "伺服器沒回應";
  }
  function diagram(round, index) {
    const all = round.events || [], milestones = all.filter(e => ["start", "done", "handoff", "decision", "blocked", "ask"].includes(e.status)).slice(-6);
    const height = 115 + Math.max(1, milestones.length) * 94 + 7 * 24;
    const svg = sv("svg", {viewBox: `0 0 320 ${height}`, class: "diagram", role: "img", "aria-labelledby": `diagram-title-${index} diagram-desc-${index}`});
    svg.append(sv("title", {id: `diagram-title-${index}`}, `${round.name}的回報里程碑。`), sv("desc", {id: `diagram-desc-${index}`}, milestones.length ? milestones.map(e => `${stamp(e.ts)}，${labels[e.status]}，${e.text}。`).join(" ") : "這輪還沒有里程碑回報。"));
    svg.append(sv("text", {x: 25, y: 31, class: "kicker"}, round.name));
    milestones.forEach((event, i) => {
      const y = 50 + i * 94, cls = event.status === "blocked" ? "warm-box" : event.status === "done" ? "blue-box" : "soft-box";
      svg.append(sv("rect", {x: 25, y, width: 270, height: 70, rx: 10, class: cls}), sv("text", {x: 160, y: y + 28, "text-anchor": "middle", class: "t"}, cut(event.text, 14)), sv("text", {x: 160, y: y + 50, "text-anchor": "middle", class: "sub"}, `${time(event.ts)}・${labels[event.status]}`));
      if (i < milestones.length - 1) svg.append(sv("path", {d: `M160 ${y + 71}v18m-4-5 4 5 4-5`, class: "line"}));
    });
    if (!milestones.length) svg.append(sv("text", {x: 160, y: 95, "text-anchor": "middle", class: "sub"}, "尚無里程碑回報"));
    bars(svg, round, 76 + Math.max(1, milestones.length) * 94);
    return svg;
  }
  function bars(parent, round, top) {
    const counts = round.counts || {}, max = Math.max(1, ...Object.values(counts));
    Object.entries(labels).filter(([key]) => key !== "none").forEach(([key, label], i) => {
      const count = counts[key] || 0, y = top + i * 24;
      parent.append(sv("text", {x: 25, y: y + 10, class: "tiny"}, label), sv("rect", {x: 85, y: y + 1, width: 170 * count / max, height: 10, rx: 3, class: key === "blocked" ? "bar-warm" : "bar"}), sv("text", {x: 290, y: y + 10, "text-anchor": "end", class: "tiny"}, count));
    });
  }

  function events(parent, list) {
    if (!list.length) { parent.append(el("p", "", "尚無回報。")); return; }
    const entries = el("ul");
    [...list].reverse().forEach(event => {
      const item = el("li", "round-event"), meta = el("div"), ts = el("time", "", stamp(event.ts)); ts.dateTime = event.ts;
      meta.append(ts, el("span", "event-state", labels[event.status] || event.status)); item.append(meta, el("p", "", event.text));
      if (event.links?.length) item.append(el("p", "event-links", event.links.join("\n")));
      entries.append(item);
    });
    parent.append(entries);
  }
  function numbers(parent, round) {
    const counts = round.counts || {}, seconds = Math.max(0, (new Date(round.last_ts) - new Date(round.first_ts)) / 1000);
    const rows = [["事件數", round.events_count], ["進度", counts.progress || 0], ["完成", counts.done || 0], ["卡住", counts.blocked || 0], ["代定", round.decisions_count], ["待你裁未答", round.asks_open || 0], ["開始", stamp(round.first_ts)], ["最近", stamp(round.last_ts)], ["歷時", Number.isFinite(seconds) ? `${Math.floor(seconds / 3600)} 小時 ${Math.floor(seconds % 3600 / 60)} 分` : "—"]];
    const table = el("table"), caption = el("caption", "visually-hidden", `${round.name}回報數字`), body = el("tbody");
    rows.forEach(([name, value]) => { const row = el("tr"), th = el("th", "", name); th.scope = "row"; row.append(th, el("td", "", value ?? 0)); body.append(row); }); table.append(caption, body); parent.append(table);
  }
  function section(parent, round, index) {
    const all = round.events || [], latest = [...all].reverse().find(e => ["progress", "done"].includes(e.status)), decisions = all.filter(e => e.status === "decision");
    const copy = el("div", "section-copy"), conclusion = el("p", "conclusion");
    parent.setAttribute("aria-labelledby", `round-heading-${index}`); parent.append(diagram(round, index), copy);
    copy.append(el("p", "chapter", `${String(index + 1).padStart(2, "0")} ／ ${round.name}`)); const heading = el("h2", "", cut(latest?.text || round.name, 40)); heading.id = `round-heading-${index}`; copy.append(heading);
    conclusion.append(el("strong", "", `${round.status === "done" ? "已完成" : round.blocked ? "卡住" : "進行中"}，最近一次 ${time(round.last_ts)}。`));
    if (decisions.length) conclusion.append(document.createTextNode(` ${decisions[decisions.length - 1].text}`));
    copy.append(conclusion);
    fold(copy, index, "numbers", "數字", body => numbers(body, round));
    fold(copy, index, "events", "全部事件", body => events(body, all));
    if (decisions.length) fold(copy, index, "decisions", "代定", body => events(body, decisions));
    if (round.blocked) fold(copy, index, "blocked", "卡住", body => events(body, all.filter(e => e.status === "blocked")));
    const report = offline ? round.report_file_url : round.report_url;
    if (safeReport(report)) copy.append(link(report, "看完整的本輪報告", "report-button"));
    copy.append(el("p", "source", "資料來源：各線回報（progress_post.sh）"));
  }
  function render(state) {
    const x = window.scrollX, y = window.scrollY, lines = state?.lines || [], line = lines.find(item => item.id === lineId) || (!lineId ? lines[0] : null);
    update(byId("line-nav"), lines.map(item => [item.id, item.title]), nav => {
      nav.append(link("index.html", "看板")); lines.forEach(item => { const a = link(`rounds.html?line=${encodeURIComponent(item.id)}`, item.title || item.id); if (item.id === line?.id) a.setAttribute("aria-current", "page"); nav.append(a); });
      if (line) nav.append(link(`detail.html?line=${encodeURIComponent(line.id)}`, "細節"));
    });
    if (!line) { update(host, ["missing", lineId], node => node.append(el("p", "round-empty", state ? "找不到這條工作線。" : "尚無進度快照。"))); connection(); return; }
    const rounds = line.rounds || [], plain = state.eli5?.main?.lines?.[line.id]?.text || "", last = rounds.find(round => round.name === line.current_round), lastEvent = last?.events?.[last.events.length - 1];
    const name = line.current_round || "尚無輪次", sentence = plain ? plain.split(/[。！？\n]/)[0] : lastEvent?.text || "尚無回報。";
    const decisionsCount = rounds.reduce((sum, round) => sum + (round.decisions_count || 0), 0), asksCount = rounds.reduce((sum, round) => sum + (round.asks_open || 0), 0);
    update(byId("masthead"), [line.title, line.current_round, last?.status, last?.last_ts, decisionsCount, asksCount, plain, lastEvent?.text], node => {
      node.append(el("p", "eyebrow", `aos ／ ${line.title || line.id} ／ 輪次進度`)); const title = el("h1", "", `${name}${last ? last.status === "done" ? "已完成" : "進行中" : ""}`); title.append(el("br"), el("span", "", sentence)); node.append(title);
      if (plain) node.append(el("p", "lead", plain));
      const meta = el("div", "meta"); [labels[last?.status] || "尚無回報", `最近更新 ${time(last?.last_ts)}`, `代定 ${decisionsCount}`, `待你裁 ${asksCount}`].forEach((text, i) => meta.append(el("span", i === 0 ? "status-pill" : "", text)));
      const live = el("span"); live.id = "round-live"; meta.append(live); node.append(meta);
    });
    document.title = `${line.title || line.id}｜輪次進度`;
    update(byId("round-nav"), rounds.map(r => r.name), nav => [...rounds].reverse().forEach((r, i) => nav.append(link(`#round-${rounds.length - 1 - i}`, r.name))));
    const valid = new Set();
    [...rounds].reverse().forEach((round, reverseIndex) => {
      const index = rounds.length - 1 - reverseIndex, id = `round-${index}`; valid.add(id); let node = byId(id);
      if (!node) { node = el("section", "report-section"); node.id = id; }
      update(node, round, container => section(container, round, index));
      const position = host.children[reverseIndex]; if (position !== node) host.insertBefore(node, position || null);
    });
    [...host.children].forEach(node => { if (!valid.has(node.id)) node.remove(); });
    if (!rounds.length) host.append(el("p", "round-empty", "這條線還沒有輪次回報。"));
    byId("source").textContent = `資料來源：各線回報（progress_post.sh）・資料時間 ${stamp(state.generated_at)}`;
    connection(); if (firstRender) revealHash(true); else window.scrollTo(x, y); firstRender = false;
  }
  document.querySelectorAll("[data-details]").forEach(button => button.addEventListener("click", () => {
    const open = button.dataset.details === "expand"; host.querySelectorAll("details").forEach(d => { d.open = open; folds.set(d.dataset.key, open); });
    byId("detail-status").textContent = open ? "細節已全部展開。" : "細節已全部收合。";
  }));
  window.addEventListener("hashchange", () => revealHash(true));
  async function poll() {
    if (polling) return; polling = true;
    try { const response = await fetch("data/state.json", {cache: "no-store"}); if (!response.ok) throw new Error(`State request failed (${response.status})`); const state = await response.json(); lastPoll = Date.now(); render(state); }
    catch (error) { console.error("rounds: error: StateReadFailed", error.message); }
    finally { polling = false; connection(); }
  }
  render(window.AOS_STATE || null);
  if (!offline) { poll(); setInterval(poll, 5000); setInterval(connection, 1000); }
})();
