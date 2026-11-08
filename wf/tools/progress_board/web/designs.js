// This script renders fable design cards from data/designs.js and refreshes them from the local server.
"use strict";
(() => {
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const tags = {"採用": "ok", "部分採用": "warn", "被翻案": "bad", "實測沒過": "bad", "進行中": "acc"};
  let signature = "";
  function fileLink(repo, doc) {
    const http = location.protocol.startsWith("http");
    const a = el("a", "", doc);
    a.href = http ? `detail.html?file=${encodeURIComponent(repo + "/" + doc)}` : `file://${repo}/${doc}`;
    return a;
  }
  function card(item, repo) {
    const box = el("article", "panel design-card"); box.id = item.id.replace(/[^\w-]/g, "_");
    const top = el("div", "title-row");
    const title = el("div"); title.append(el("p", "meta", [item.topic, item.date].filter(Boolean).join("｜")), el("h2", "", item.title));
    top.append(title);
    if (item.outcome_tag) top.append(el("span", `tag tag-${tags[item.outcome_tag] || "muted"}`, item.outcome_tag));
    if (item.pending) top.append(el("span", "tag tag-muted", "還沒寫卡"));
    box.append(top);
    if (item.conclusion) box.append(el("p", "conclusion", item.conclusion));
    if (item.figure_svg) { const fig = el("figure", "figure"); fig.innerHTML = item.figure_svg; box.append(fig); }
    if (item.figures) item.figures.forEach(extra => {
      const fig = el("figure", "figure"); fig.innerHTML = extra.svg; if (extra.caption) fig.append(el("figcaption", "meta", extra.caption)); box.append(fig);
    });
    if (item.eli5) { const e = el("div", "eli5-box"); e.append(el("strong", "", "白話"), el("p", "", item.eli5)); box.append(e); }
    if (item.outcome) { const o = el("div", "outcome"); o.append(el("strong", "", "後來怎樣了"), el("p", "", item.outcome)); box.append(o); }
    const more = el("details"); more.append(el("summary", "", "細節、數字與原檔"));
    const src = el("p", "meta"); src.append("原檔："); src.append(fileLink(repo, item.doc)); if (item.exists === false) src.append("（檔案不見了）"); more.append(src);
    if (item.details_md) { const body = el("div", "md"); body.append(window.AosMd ? window.AosMd.render(item.details_md) : el("pre", "", item.details_md)); more.append(body); }
    box.append(more);
    return box;
  }
  function render(data) {
    const next = JSON.stringify(data); if (next === signature) return; signature = next;
    const host = document.getElementById("cards"), toc = document.getElementById("toc");
    const open = new Set([...host.querySelectorAll("details[open]")].map(d => d.closest("article").id));
    host.replaceChildren(); toc.replaceChildren();
    if (!data) { host.append(el("p", "banner", "還沒有設計資料；請依 README 跑 collect。")); return; }
    data.cards.forEach(item => {
      const node = card(item, data.repo); host.append(node);
      if (open.has(node.id)) node.querySelector("details").open = true;
      const a = el("a", "button", item.title); a.href = `#${node.id}`; toc.append(a);
    });
    document.getElementById("stamp").textContent = `${data.cards.length - data.pending} 張卡｜${data.pending} 份新設計還沒寫卡`;
  }
  render(window.AOS_DESIGNS);
  if (location.hash) setTimeout(() => { const t = document.getElementById(location.hash.slice(1)); if (t) t.scrollIntoView(); }, 50);
  if (location.protocol.startsWith("http")) setInterval(async () => {
    try { const r = await fetch(`data/designs.json?t=${Date.now()}`, {cache: "no-store"}); if (r.ok) render(await r.json()); } catch (_) { /* keep the last view */ }
  }, 30000);
})();
