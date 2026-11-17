// 全景頁 frontend: plain JS, zero dependencies, no build step (API contract: ../API.md).
//
// Modules (each panel owns one DOM root and one render function):
//   api()           fetch helper: GET/POST JSON, X-View-Token, TokenBad -> new session + retry once
//   el()            tiny DOM builder; data only ever goes in via textContent / text nodes
//   renderHeader()  sticky big numbers + "更新於" + red banner        -> #hdr, #banner
//   renderAsks()    🔵 要你決定: one card per ASK, keyed by letter      -> #asks
//   renderTree()    🏢 部門與員工: renderNode() recursive, any depth     -> #tree
//   renderMachine() ⚙️ 機房: proc roots + llm workers                   -> #machine
//   renderRelay()   📮 隊伍回覆                                         -> #relay
//   Panel           #agent=NAME side panel: 現在 / 往來 / 對話紀錄 + 說一句話 / 寄信 / 董事長指令 (orderForm)
//   map.js          phase 0b 地圖 (separate file, loaded after this one)           -> #map
//   refresh()       every 15 s: /api/tree + /api/asks + /api/relay, then renderAll()
// Re-render rules: ask cards that already exist are never rebuilt (so typing is safe);
// the tree/relay keep their open/closed state; the scroll position is restored.
// To add a panel later (zoom map, departments/tags, HR hire, power budget): add a
// <section> in index.html, a renderX() here, its fetch in refresh(), a call in renderAll().
'use strict';

const POLL_MS = 15000;
const STALE_S = 180;
const ICON = { red: '🔴', blue: '🔵', yellow: '🟡', green: '🟢', gray: '⚪' };
const LIGHT_WORD = { red: '出事', blue: '等你', yellow: '留意', green: '正常', gray: '停了' };
const KIND_WORD = { decide: '要決定', verify: '請你驗', trial: '請你試', chore: '請你做', fyi: '告知' };
const MAIL_STATUS = ['REQUEST', 'PROGRESS', 'DONE', 'BLOCKED', 'NEEDS-USER', 'FAILED'];
const OPEN_KEY = 'aosview.open';

const S = {
  token: null, tree: null, treeErr: null, asks: [], relay: [],
  failMsg: null, open: loadOpen(), relayOpen: new Set(), refreshing: false,
};

// ---------- helpers ----------

const $ = (sel) => document.querySelector(sel);
const nowS = () => Date.now() / 1000;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = String(v);
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (typeof v !== 'string' && k in e) e[k] = v; // checked, disabled, rows, hidden...
    else e.setAttribute(k, v);
  }
  for (const c of kids.flat(Infinity)) {
    if (c == null || c === false) continue;
    e.append(c instanceof Node ? c : String(c));
  }
  return e;
}

function ago(t) {
  if (!t) return 'unknown';
  const d = Math.max(0, Math.floor(nowS() - t));
  if (d < 60) return d + 's ago';
  if (d < 3600) return Math.floor(d / 60) + 'm ago';
  if (d < 86400) return Math.floor(d / 3600) + 'h ' + Math.floor((d % 3600) / 60) + 'm ago';
  return Math.floor(d / 86400) + 'd ago';
}

function show(box, text, ok) {
  box.className = 'result ' + (ok === true ? 'ok' : ok === false ? 'bad' : 'mut');
  box.textContent = text || '';
}

// a form is "busy" if it has focus or the user typed / picked something in it
function busy(root) {
  if (root.contains(document.activeElement) && document.activeElement !== document.body) return true;
  if (root.dataset.dirty === '1') return true;
  return [...root.querySelectorAll('input[type=text], textarea')].some((x) => x.value.trim() !== '');
}

function loadOpen() {
  try { return JSON.parse(localStorage.getItem(OPEN_KEY) || '{}') || {}; } catch (e) { return {}; }
}
function saveOpen() {
  try { localStorage.setItem(OPEN_KEY, JSON.stringify(S.open)); } catch (e) { /* private mode */ }
}

// ---------- api ----------

class ApiError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

async function getSession() {
  const r = await fetch('/api/session', { credentials: 'same-origin', cache: 'no-store' });
  if (!r.ok) throw new ApiError('SessionBad', '拿不到連線憑證（HTTP ' + r.status + '）');
  const j = await r.json();
  S.token = j.token;
  return j;
}

// api(path) = GET; api(path, body) = POST JSON with the session token.
async function api(path, body, retried) {
  const post = body !== undefined;
  const opt = { credentials: 'same-origin', cache: 'no-store' };
  if (post) {
    if (!S.token) await getSession();
    opt.method = 'POST';
    opt.headers = { 'Content-Type': 'application/json', 'X-View-Token': S.token };
    opt.body = JSON.stringify(body);
  }
  let r;
  try { r = await fetch(path, opt); } catch (e) {
    throw new ApiError('NetworkBad', '連不上全景頁的後端（' + e.message + '）');
  }
  let j = null;
  try { j = await r.json(); } catch (e) { /* not JSON */ }
  if (post && r.status === 403 && j && j.error === 'TokenBad' && !retried) {
    await getSession();
    return api(path, body, true);
  }
  if (!r.ok || !j || j.ok === false) {
    const code = (j && j.error) || 'HTTP' + r.status;
    throw new ApiError(code, (j && j.message) || '後端回 HTTP ' + r.status + (j ? '' : '（不是 JSON）'));
  }
  return j;
}

// ---------- header ----------

function bigNum(n, label, cls, href) {
  const num = el('b', { text: n });
  return el('div', { class: 'big ' + (cls || '') }, href ? el('a', { href }, num) : num, el('span', { text: label }));
}

function renderHeader() {
  const t = S.tree;
  const nodes = t ? Object.values(t.nodes || {}) : [];
  const agents = nodes.filter((n) => n.kind === 'agent');
  const running = agents.filter((n) => String(n.state || '').toLowerCase() === 'running').length;
  const red = nodes.filter((n) => n.light === 'red').length;
  const yellow = nodes.filter((n) => n.light === 'yellow').length;
  $('#hdr').replaceChildren(
    el('h1', { text: '全景' }),
    bigNum(S.asks.length, '要你決定', 'ask' + (S.asks.length ? ' hot' : ''), '#asks-sec'),
    bigNum(red, '🔴 出事', red ? 'hot' : ''),
    bigNum(yellow, '🟡 要留意', yellow ? 'warn' : ''),
    bigNum(running, 'agent 在跑'),
    el('span', { class: 'mut', text: '（另有 proc ' + (nodes.length - agents.length) + ' 個、llm 工作 ' + (t ? t.llm_workers || 0 : 0) + ' 個）' }),
    el('span', { id: 'fresh', class: 'fresh mut' }));
  tickFresh();
}

// runs every second: freshness text and the red banner
function tickFresh() {
  const t = S.tree;
  const f = $('#fresh');
  if (f) f.textContent = t ? '更新於 ' + Math.max(0, Math.floor(nowS() - t.generated_at)) + ' 秒前（每 15 秒）' : '';
  const msgs = [];
  if (S.failMsg) msgs.push('⚠️ 最近一次更新失敗：' + S.failMsg);
  if (S.treeErr) msgs.push('⚠️ 讀 daemon 表失敗：' + S.treeErr);
  if (t && nowS() - t.generated_at > STALE_S) {
    msgs.push('⚠️ 資料已經 ' + Math.floor((nowS() - t.generated_at) / 60) + ' 分鐘沒更新，畫面上的狀態可能是舊的');
  }
  const b = $('#banner');
  b.hidden = msgs.length === 0;
  b.textContent = msgs.join('　');
}

// ---------- 🔵 asks ----------

let uid = 0;

const SENT_ASKS = new Set(); // letters answered on this page: never shown again, even if a stale list still has them

function renderAsks() {
  const root = $('#asks');
  const asks = S.asks.filter((a) => !SENT_ASKS.has(a.letter));
  $('#asks-count').textContent = '（' + asks.length + '）';
  $('#asks-empty').hidden = asks.length > 0;
  const want = new Set(asks.map((a) => a.letter));
  const have = new Map([...root.children].map((c) => [c.dataset.letter, c]));
  for (const [letter, card] of have) {
    if (want.has(letter)) continue;
    if (busy(card)) markGone(card); else card.remove();
  }
  let prev = null;
  for (const a of asks) {
    let card = have.get(a.letter);
    if (!card || !card.isConnected) card = askCard(a);
    const ref = prev ? prev.nextSibling : root.firstChild;
    // never move the card the user is typing in (moving would drop the focus)
    if (card !== ref && !(card.isConnected && card.contains(document.activeElement))) root.insertBefore(card, ref);
    prev = card;
  }
}

function markGone(card) {
  if (card.classList.contains('gone')) return;
  card.classList.add('gone');
  card.prepend(el('div', { class: 'mut', text: '（這封信已經不在等你的清單上，可能在別處回過了；你寫的字先留著）' }));
}

function askCard(a) {
  const id = 'a' + (++uid);
  const card = el('div', { class: 'card ask' + (a.urgent ? ' urgent' : '') });
  card.dataset.letter = a.letter;
  card.addEventListener('input', () => { card.dataset.dirty = '1'; });
  const meta = ['from ' + (a.from || '?'), KIND_WORD[a.kind] || a.kind, ago(a.sent_at),
    a.deadline ? '期限 ' + a.deadline : null, a.same > 1 ? '同類 ' + a.same + ' 封' : null].filter(Boolean).join(' · ');
  card.append(el('div', { class: 'ask-head' },
    a.urgent ? '❗ ' : '', a.unseen ? el('span', { class: 'tag new', text: '新' }) : null,
    el('b', { text: a.title || '（沒有標題）' }), ' ', el('span', { class: 'mut', text: meta })));
  if (a.risk === 'irreversible') card.append(el('div', { class: 'warn', text: '⚠️ 不可逆：每題都要你親手選，沒有預選' }));
  if (a.decide) card.append(el('div', { class: 'decide' }, '要你決定的：', el('b', { text: a.decide })));
  if (a.what) card.append(el('details', {}, el('summary', { class: 'mut', text: '背景內容' }), el('pre', { text: a.what })));

  const form = el('form', {});
  const msg = el('div', { class: 'result' });
  const qs = a.questions || [];
  let payload;
  if (qs.length) {
    for (const q of qs) form.append(questionBox(q, id, a.risk === 'irreversible'));
    const note = el('input', { type: 'text', name: 'note', placeholder: '備註（可空）' });
    form.append(el('div', { class: 'form-row' }, note, el('button', { class: 'primary', text: '送出' })));
    payload = () => {
      const answers = {};
      for (const q of qs) {
        const r = form.querySelector('input[name="' + CSS.escape(id + '_' + q.id) + '"]:checked');
        if (!r) throw new Error('第 ' + q.id + ' 題還沒選');
        answers[q.id] = r.value;
      }
      return { letter: a.letter, do: 'answer', answers, note: note.value.trim() };
    };
  } else if (a.kind === 'fyi') {
    form.append(el('div', { class: 'form-row' }, el('button', { text: '知道了，收起來' })));
    payload = () => ({ letter: a.letter, do: 'ok' });
  } else {
    const ta = el('textarea', { rows: 2, placeholder: '用你的話回' });
    form.append(ta, el('div', { class: 'form-row' }, el('button', { class: 'primary', text: '回覆' })));
    payload = () => {
      if (!ta.value.trim()) throw new Error('回覆是空的');
      return { letter: a.letter, do: 'reply', text: ta.value.trim() };
    };
  }
  form.addEventListener('submit', (ev) => { ev.preventDefault(); submitAsk(a, card, form, msg, payload); });
  card.append(form, msg);
  return card;
}

async function loadAnswered() {
  try {
    const d = await api('/api/answered');
    S.answered = d.answered || [];
  } catch (e) { return; }
  renderAnswered();
}

function renderAnswered() {
  const list = $('#answered-list');
  if (!list || busy(list)) return; // do not redraw while a correction is being typed
  const xs = S.answered || [];
  $('#answered-count').textContent = '（最近 24 小時 ' + xs.length + ' 封）';
  if (!xs.length) { list.replaceChildren(el('div', { class: 'mut', text: '最近 24 小時沒有從這頁送出的回答。' })); return; }
  list.replaceChildren(...xs.map((x) => {
    const DO = { answer: '答題', reply: '回覆', ok: '收起來' };
    const row = el('div', { class: 'card answered-row' },
      el('div', {}, el('b', { text: x.title || x.letter }), ' ',
        el('span', { class: 'mut', text: (x.from ? 'from ' + x.from + ' · ' : '') + (DO[x.do] || x.do) + ' · ' + ago(x.at) })),
      el('div', { class: 'mut', text: '我送的：' + ((x.answers || []).join(' ') || '-') }));
    if (x.from && x.do !== 'ok') {
      const ta = el('textarea', { rows: 2, placeholder: '要改答案或補充，寫在這裡；會寄一封「更正」給 ' + x.from });
      const btn = el('button', { type: 'button', text: '寄更正' });
      const msg = el('div', {});
      btn.addEventListener('click', async () => {
        const t = ta.value.trim();
        if (!t) { show(msg, '沒有內容', false); return; }
        btn.disabled = true; show(msg, '送出中…');
        try {
          const r = await api('/api/mail', { name: x.from, status: 'REQUEST', title: '更正：' + (x.title || x.letter),
            what: '我剛才在全景頁回答了「' + (x.title || x.letter) + '」（信名 ' + x.letter + '，我送的：' +
              ((x.answers || []).join(' ') || '-') + '）。更正如下，以這封為準：\n\n' + t });
          show(msg, '✅ ' + (r.message || '已寄出') + '；回覆會出現在它的「往來」', true);
          ta.value = ''; delete list.dataset.dirty;
        } catch (e) { show(msg, '寄不出去：' + e.message, false); }
        btn.disabled = false;
      });
      ta.addEventListener('input', () => { list.dataset.dirty = '1'; });
      row.append(el('details', {}, el('summary', { class: 'mut', text: '✏️ 改答案或補充（寄更正給 ' + x.from + '）' }), ta, el('div', {}, btn), msg));
    }
    return row;
  }));
}

function questionBox(q, id, irreversible) {
  const box = el('div', { class: 'q' },
    el('div', {}, el('b', { text: q.id }), ' ', q.question || ''),
    q.eli5 ? el('div', { class: 'eli5', text: q.eli5 }) : null);
  for (const o of q.options || []) {
    const rec = o.key === q.recommend;
    box.append(el('label', { class: 'opt' },
      el('input', { type: 'radio', name: id + '_' + q.id, value: o.key, checked: rec && !irreversible }),
      ' ', el('b', { text: o.key }), ' ', o.label || '',
      rec ? el('span', { class: 'rec', text: '推薦' }) : null,
      o.consequence ? el('span', { class: 'conseq', text: '→ ' + o.consequence }) : null));
  }
  if (q.why) box.append(el('div', { class: 'mut', text: '為什麼推薦：' + q.why }));
  return box;
}

async function submitAsk(a, card, form, msg, payload) {
  let body;
  try { body = payload(); } catch (e) { show(msg, e.message, false); return; }
  const btn = form.querySelector('button');
  btn.disabled = true;
  show(msg, '送出中…');
  try {
    const r = await api('/api/answer', body);
    SENT_ASKS.add(a.letter);
    flash($('#asks-flash'), '✅ ' + (r.message || '已送出：' + (a.title || '')) + '（收進上面的「📤 已送出的回答」）', true);
    // keep the page still: remove the card and scroll up by its height if it was above the viewport
    const h = card.getBoundingClientRect();
    card.remove();
    if (h.bottom < 0) window.scrollBy(0, -h.height);
    $('#asks-count').textContent = '（' + S.asks.filter((x) => !SENT_ASKS.has(x.letter)).length + '）';
    loadAnswered();
    refresh();
  } catch (e) {
    show(msg, '送出失敗：' + e.message + (e.code ? '（' + e.code + '）' : ''), false);
    btn.disabled = false;
  }
}

function flash(box, text, ok) {
  const f = el('div', { class: 'flash ' + (ok ? 'ok' : 'bad'), text });
  box.prepend(f);
  setTimeout(() => f.remove(), 12000);
}

// ---------- 🏢 tree (same component at every depth) ----------

function renderTree() {
  const t = S.tree;
  if (!t) { $('#tree').replaceChildren(el('div', { class: 'mut', text: '還沒讀到 daemon 表。' })); return; }
  const roots = (t.roots || []).filter((id) => t.nodes[id] && t.nodes[id].kind === 'agent');
  $('#tree').replaceChildren(...roots.map((id) => renderNode(id, t.nodes, 0, new Set())).filter(Boolean));
}

function defaultOpen(depth, worst) { return depth === 0 || worst === 'red' || worst === 'blue'; }

function renderNode(id, nodes, depth, path) {
  const n = nodes[id];
  if (!n || path.has(id)) return null; // guard against bad data loops
  const seen = new Set(path).add(id);
  const kids = (n.children || []).filter((c) => nodes[c]);
  const r = n.rollup || { worst: n.light, nodes: 1 };
  const row = el('span', { class: 'row' },
    el('span', { title: LIGHT_WORD[n.light] || '', text: ICON[n.light] || '⚪' }),
    n.kind === 'agent'
      ? el('a', { class: 'nm', href: '#agent=' + encodeURIComponent(id), text: id })
      : el('span', { class: 'nm', text: id }),
    kids.length ? el('span', { class: 'mut', text: '（底下 ' + (r.nodes - 1) + ' 個，最差 ' + (ICON[r.worst] || '⚪') + '）' }) : null,
    el('span', { class: 'mut', text: [n.kind, n.busy || n.state || '?', 'queue ' + (n.queued == null ? '-' : n.queued), '動靜 ' + ago(n.active_at)].join(' · ') }),
    n.asks ? el('span', { class: 'tag blue', text: '等你 ' + n.asks }) : null,
    el('span', { class: 'why light-' + n.light, text: n.why || '' }));
  const lines = [];
  const rep = (n.reports || [])[0];
  if (rep) lines.push(el('div', { class: 'line', title: rep.title || '' }, '📮 最近回報：', el('b', { text: rep.title || '' }), ' ', el('span', { class: 'mut', text: ago(rep.sent_at) })));
  if (n.note) {
    const nt = n.note, at = typeof nt.at === 'number' ? nt.at : (Date.parse(nt.at) / 1000 || null);
    lines.push(el('div', { class: 'line', title: nt.text || '' }, '📝 隊長留話：', el('b', { text: nt.text || '' }),
      ' ', el('span', { class: 'mut', text: '（' + (nt.status || '') + (nt.on ? '，等 ' + nt.on : '') + '，' + ago(at) + '）' })));
  }
  if (n.team_light) lines.push(el('div', { class: 'line why light-' + n.team_light.light, text: (ICON[n.team_light.light] || '') + ' ' + (n.team_light.why || '') }));
  if (n.aide) lines.push(el('div', { class: 'line mut', text: '🤝 小助手 ' + n.aide.name + ' · 心跳 ' + ago(n.aide.last_beat) + (n.passed ? ' · 已轉 ' + n.passed + ' 張決策單' : '') }));
  if (n.last_answer) lines.push(el('div', { class: 'line mut', title: n.last_answer, text: '💬 最後一句：' + n.last_answer }));
  if (!kids.length) return el('div', { class: 'node leaf' }, row, lines);

  const def = defaultOpen(depth, r.worst);
  const d = el('details', { class: 'node' });
  d.open = id in S.open ? S.open[id] : def;
  d.addEventListener('toggle', () => {
    // remember only choices that differ from the automatic rule
    if (d.open === def) delete S.open[id]; else S.open[id] = d.open;
    saveOpen();
  });
  d.append(el('summary', {}, row, ...lines),
    el('div', { class: 'kids' }, kids.map((c) => renderNode(c, nodes, depth + 1, seen))));
  return d;
}

// ---------- ⚙️ machine room ----------

function renderMachine() {
  const t = S.tree;
  if (!t) { $('#machine').replaceChildren(); return; }
  const procs = (t.roots || []).filter((id) => t.nodes[id] && t.nodes[id].kind !== 'agent');
  $('#machine').replaceChildren(
    ...procs.map((id) => renderNode(id, t.nodes, 0, new Set())).filter(Boolean),
    procs.length ? '' : el('div', { class: 'mut', text: '沒有普通 proc。' }),
    el('div', { class: 'node leaf mut', text: '🧠 llm 單次工作 ' + (t.llm_workers || 0) + ' 個' }));
}

// ---------- 📮 relay ----------

const DELIVERY = { queued: '排隊中', read: '已讀', replied: '已回覆', unknown: '狀態不明' };
const DELIVERY_WHY = {
  queued: '已送到對方的信箱或 queue，正在排隊；對方還沒收進對話',
  read: '對方已經收進對話（信已從信箱拿走／這句話已在對話紀錄裡）',
  replied: '對方已經回到全景頁的信箱',
  unknown: '查不到（對方的信箱或對話紀錄讀不到）',
};

function letterLine(x, openSet) {
  const arrow = x.dir === 'out' ? '➡️ 我' + (x.kind === 'say' ? '說' : x.kind === 'order' ? '下指令' : '寄') : '⬅️ 回覆';
  const who = x.dir === 'out' ? '給 ' + (x.to || '?') : 'from ' + (x.from || '?');
  const title = x.kind === 'say' && x.dir === 'out' ? '' : x.title || '';
  const sum = el('summary', {},
    el('span', { class: 'dir', text: arrow }),
    x.status ? el('span', { class: 'tag st', text: x.status }) : null,
    x.dir === 'out' && DELIVERY[x.delivery] ? el('span', { class: 'tag dl dl-' + x.delivery, text: DELIVERY[x.delivery] + (x.delivery === 'queued' && x.queue_ahead != null ? '（前面還有 ' + x.queue_ahead + ' 則）' : ''), title: DELIVERY_WHY[x.delivery] }) : null,
    el('b', { text: title }), ' ', el('span', { class: 'mut', text: who + ' · ' + ago(x.sent_at) }));
  const d = el('details', { class: 'letter' }, sum, el('pre', { text: x.what || '（沒有內容）' }));
  if (x.kind === 'say' && x.dir === 'out') d.open = true; // a said line is short: show it
  if (openSet) {
    if (openSet.has(x.letter)) d.open = true;
    d.addEventListener('toggle', () => { if (d.open) openSet.add(x.letter); else openSet.delete(x.letter); });
  }
  return d;
}

function renderRelay() {
  const list = S.relay || [];
  if (!list.length) {
    $('#relay').replaceChildren(el('div', { class: 'card mut', text: '還沒有。隊伍回信到中轉信箱就會出現在這裡。' }));
    return;
  }
  const first = list.slice(0, 20), rest = list.slice(20);
  const card = el('div', { class: 'card' }, first.map((x) => letterLine(x, S.relayOpen)));
  if (rest.length) card.append(el('details', {}, el('summary', { class: 'mut', text: '更早的 ' + rest.length + ' 封' }), rest.map((x) => letterLine(x, S.relayOpen))));
  $('#relay').replaceChildren(card);
}

// ---------- agent side panel (#agent=NAME) ----------

const Panel = { name: null, tab: 'now', parts: null };

function route() {
  const m = location.hash.match(/^#agent=(.+)$/);
  let name = null;
  if (m) { try { name = decodeURIComponent(m[1]); } catch (e) { name = null; } }
  if (name === Panel.name) return;
  Panel.name = name;
  if (!name) { $('#panel').hidden = true; $('#panel').replaceChildren(); return; }
  openPanel(name);
}

function closePanel() {
  if (location.hash) history.pushState(null, '', location.pathname + location.search);
  Panel.name = null;
  $('#panel').hidden = true;
  $('#panel').replaceChildren();
}

function openPanel(name) {
  const node = S.tree && S.tree.nodes[name];
  const p = {
    now: el('div', {}), thread: el('div', {}), hist: el('div', {}),
    sayMsg: el('div', { class: 'result' }), mailMsg: el('div', { class: 'result' }),
  };
  Panel.parts = p;
  const tabs = el('div', { class: 'tabs' });
  const body = el('div', { class: 'p-body' }, p.now, p.thread, p.hist);
  const setTab = (k) => {
    Panel.tab = k;
    for (const [key, box] of [['now', p.now], ['thread', p.thread], ['hist', p.hist]]) box.hidden = key !== k;
    for (const b of tabs.children) b.classList.toggle('on', b.dataset.k === k);
  };
  for (const [k, label] of [['now', '現在'], ['thread', '往來'], ['hist', '對話紀錄']]) {
    const b = el('button', { type: 'button', text: label, onclick: () => setTab(k) });
    b.dataset.k = k;
    tabs.append(b);
  }
  $('#panel').replaceChildren(
    el('div', { class: 'p-head' },
      el('span', { text: node ? ICON[node.light] || '⚪' : '❔' }),
      el('h3', { text: name }),
      el('button', { type: 'button', text: '🔄 重新讀', onclick: () => loadPanel(name) }),
      el('button', { type: 'button', text: '✕', title: '關閉（Esc）', onclick: closePanel })),
    el('div', { class: 'p-acts' }, sayForm(name, p.sayMsg), p.sayMsg, mailForm(name, p.mailMsg), p.mailMsg,
      orderForm(name, p.orderMsg = el('div', { class: 'result' })), p.orderMsg),
    tabs, body);
  setTab(Panel.tab);
  $('#panel').hidden = false;
  loadPanel(name);
}

async function loadPanel(name) {
  const p = Panel.parts;
  p.now.replaceChildren(el('div', { class: 'mut', text: '讀取中…（要幾秒）' }));
  p.hist.replaceChildren(el('div', { class: 'mut', text: '讀取中…' }));
  loadThread(name);
  let d;
  try { d = await api('/api/agent?name=' + encodeURIComponent(name)); } catch (e) {
    if (Panel.name !== name) return;
    const bad = el('div', { class: 'result bad', text: '讀不到 ' + name + '：' + e.message });
    p.now.replaceChildren(bad);
    p.hist.replaceChildren(bad.cloneNode(true));
    return;
  }
  if (Panel.name !== name) return; // user already switched to another agent
  renderAgentNow(p.now, d);
  renderHistory(p.hist, d.history || []);
}

async function loadThread(name) {
  const box = Panel.parts.thread;
  box.replaceChildren(el('div', { class: 'mut', text: '讀取中…' }));
  try {
    const d = await api('/api/thread?name=' + encodeURIComponent(name));
    if (Panel.name === name) {
      renderThread(box, d.letters || []);
      if (d.turn) {
        const t = d.turn;
        const txt = '對方正在一輪裡' + (t.busy ? '（' + t.busy + '）' : '') + '：queue 裡有 ' + t.queued +
          ' 則在等，這一輪做完才會讀。最後動靜 ' + (t.active_at ? ago(t.active_at) : '沒有紀錄') + '。這不是掛了。';
        box.prepend(el('div', { class: 'turn-note', text: txt }));
      }
    }
  } catch (e) {
    if (Panel.name === name) box.replaceChildren(el('div', { class: 'result bad', text: '讀不到往來：' + e.message }));
  }
}

function renderAgentNow(box, d) {
  const s = d.now || {};
  const kv = el('dl', { class: 'kv' });
  const add = (k, v) => kv.append(el('dt', { text: k }), el('dd', { text: v == null || v === '' ? '-' : v }));
  add('狀態', s.state); add('phase', s.phase); add('在做', s.busy || '閒著');
  add('排隊', s.queued); add('pid', s.pid);
  add('記憶體', s.memory_mb == null ? null : s.memory_mb + ' MB');
  add('上線', s.up_min == null ? null : s.up_min + ' 分鐘');
  add('workspace', s.workspace);
  const mb = d.mailbox || {};
  box.replaceChildren(kv,
    el('h4', { text: '💬 最後一句' }), el('pre', { text: s.last_answer || '（還沒有）' }),
    el('h4', { text: '📥 信箱裡等著的（' + (mb.waiting || 0) + '）' }),
    (mb.letters || []).length
      ? el('div', {}, mb.letters.map((x) => el('div', { class: 'letter' },
        x.status ? el('span', { class: 'tag st', text: x.status }) : null, el('b', { text: x.title || '' }), ' ',
        el('span', { class: 'mut', text: 'from ' + (x.from || '?') + ' · ' + ago(x.sent_at) }))))
      : el('div', { class: 'mut', text: '沒有。' }));
}

// out letters with their replies (in_reply_to) grouped under them; threads newest first
function renderThread(box, letters) {
  const outs = new Map();
  const threads = [];
  for (const x of letters) {
    if (x.dir !== 'out') continue;
    const th = { root: x, replies: [], last: x.sent_at || 0 };
    outs.set(x.letter, th);
    threads.push(th);
  }
  for (const x of letters) {
    if (x.dir === 'out') continue;
    const th = x.in_reply_to && outs.get(x.in_reply_to);
    if (th) { th.replies.push(x); th.last = Math.max(th.last, x.sent_at || 0); } else threads.push({ root: x, replies: [], last: x.sent_at || 0 });
  }
  threads.sort((a, b) => b.last - a.last);
  if (!threads.length) { box.replaceChildren(el('div', { class: 'mut', text: '你跟它還沒有往來。用上面的「說一句話」或「寄信」開始。' })); return; }
  box.replaceChildren(...threads.map((th) => el('div', { class: 'thread' },
    letterLine(th.root),
    th.replies.sort((a, b) => (a.sent_at || 0) - (b.sent_at || 0)).map((x) => {
      const l = letterLine(x);
      l.classList.add('reply');
      return l;
    }))));
}

function renderHistory(box, hist) {
  if (!hist.length) { box.replaceChildren(el('div', { class: 'mut', text: '沒有紀錄。' })); return; }
  box.replaceChildren(el('div', { class: 'mut', text: '新的在上，最多 30 則，每則最多 600 字。' }),
    ...hist.map((h) => el('div', { class: 'msg' },
      el('span', { class: 'role ' + (h.role || ''), text: '#' + h.line + ' ' + (h.role || '?') }),
      (h.tools || []).length ? el('span', { class: 'tools', text: '🔧 ' + h.tools.join(', ') }) : null,
      h.text ? el('pre', { text: h.text }) : null)));
}

function sayForm(name, msg) {
  const input = el('input', { type: 'text', placeholder: '對 ' + name + ' 說一句話（會自動加前綴、附上怎麼回）' });
  const btn = el('button', { class: 'primary', text: '說' });
  const f = el('form', { class: 'form-row' }, el('b', { text: '💬 說一句話' }), input, btn);
  f.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const text = input.value.trim();
    if (!text) { show(msg, '沒有內容', false); return; }
    btn.disabled = true; show(msg, '送出中…');
    try {
      const r = await api('/api/say', { name, text });
      show(msg, '✅ ' + (r.message || '已送出'), true);
      input.value = '';
      if (Panel.name === name) loadThread(name);
    } catch (e) { show(msg, '送出失敗：' + e.message, false); }
    btn.disabled = false;
  });
  return f;
}

function mailForm(name, msg) {
  const status = el('select', {}, MAIL_STATUS.map((s) => el('option', { value: s, text: s })));
  status.value = 'REQUEST';
  const title = el('input', { type: 'text', placeholder: '標題' });
  const what = el('textarea', { rows: 4, placeholder: '內容：要它做什麼、做到哪裡算完' });
  const btn = el('button', { class: 'primary', text: '寄出' });
  const f = el('form', { class: 'mail-form' }, el('div', { class: 'form-row' }, status, title), what, el('div', {}, btn));
  f.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!title.value.trim()) { show(msg, '標題是空的', false); return; }
    btn.disabled = true; show(msg, '寄送中…');
    try {
      const r = await api('/api/mail', { name, status: status.value, title: title.value.trim(), what: what.value });
      show(msg, '✅ ' + (r.message || '已寄出'), true);
      title.value = ''; what.value = ''; status.value = 'REQUEST';
      if (Panel.name === name) loadThread(name);
    } catch (e) { show(msg, '寄送失敗：' + e.message, false); }
    btn.disabled = false;
  });
  return el('details', {}, el('summary', { text: '✉️ 寄信（正式交辦，回信會出現在「往來」）' }), f);
}

// ---------- chairman's orders (expand / HR hire / power) ----------
// The page only sends one REQUEST letter to whoever takes that kind of order (GET /api/orders);
// the receiver changes the tree through its own rules (gate). See API.md "Chairman's orders".
const ORDER_FIELD_WORD = { budget: '預算（可空）', role: '要什麼角色', model: '用哪個模型（sol／astra／…）',
  count: '幾個', priority: '優先級（高／中／低）', quota: '額度（可空）' };
let ORDER_KINDS = null;

function orderForm(name, msg) {
  const kindSel = el('select', {});
  const fields = el('div', {});
  const what = el('textarea', { rows: 3, placeholder: '要什麼、為什麼' });
  const btn = el('button', { class: 'primary', text: '下指令' });
  const inputs = {};
  const drawFields = () => {
    const k = (ORDER_KINDS || []).find((x) => x.kind === kindSel.value);
    fields.replaceChildren();
    for (const key of Object.keys(inputs)) delete inputs[key];
    if (!k) return;
    const to = k.to || name;
    fields.append(el('div', { class: 'mut', text: '這張單會寄給 ' + to + '，由它照自己的規矩去做（要加人的會走 gate）' }));
    for (const f of k.fields) {
      inputs[f] = el('input', { type: 'text', placeholder: ORDER_FIELD_WORD[f] || f });
      fields.append(el('div', { class: 'form-row' }, inputs[f]));
    }
  };
  const fill = async () => {
    try {
      if (!ORDER_KINDS) ORDER_KINDS = (await api('/api/orders')).kinds || [];
      kindSel.replaceChildren(...ORDER_KINDS.map((k) => el('option', { value: k.kind, text: k.label })));
      drawFields();
    } catch (e) { show(msg, '讀不到指令種類：' + e.message, false); }
  };
  kindSel.addEventListener('change', drawFields);
  const f = el('form', { class: 'mail-form' }, el('div', { class: 'form-row' }, kindSel), fields, what, el('div', {}, btn));
  f.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if (!what.value.trim()) { show(msg, '要寫清楚要什麼', false); return; }
    const body = { kind: kindSel.value, target: name, what: what.value.trim() };
    for (const [k, inp] of Object.entries(inputs)) if (inp.value.trim()) body[k] = inp.value.trim();
    btn.disabled = true; show(msg, '送出中…');
    try {
      const r = await api('/api/order', body);
      show(msg, '✅ ' + (r.message || '已送出'), true);
      what.value = ''; for (const inp of Object.values(inputs)) inp.value = '';
      if (Panel.name === name) loadThread(name);
    } catch (e) { show(msg, '送出失敗：' + e.message, false); }
    btn.disabled = false;
  });
  const d = el('details', {}, el('summary', { text: '🏛️ 董事長指令（擴充這個部門／加人／llm 額度）' }), f);
  d.addEventListener('toggle', () => { if (d.open && !kindSel.options.length) fill(); });
  return d;
}

// ---------- 📌 the user's board ----------

const Board = { built: false, now: null, input: null, back: null, msg: null };

function renderBoard() {
  const box = $('#board');
  if (!box) return;
  if (!Board.built) {
    Board.now = el('div', { class: 'board-now' });
    Board.input = el('textarea', { rows: '2', maxlength: '1000', placeholder: '例如：我去睡午覺，有事先寄信，我醒了會看。' });
    Board.back = el('input', { type: 'text', maxlength: '100', placeholder: '預計回來（可空），例如 15:30' });
    Board.msg = el('div', {});
    const put = async (text, back) => {
      show(Board.msg, '送出中…');
      try {
        const r = await api('/api/board', { text, back });
        S.board = r.user || null;
        show(Board.msg, '✅ ' + (r.message || '好了'), true);
        Board.input.value = ''; Board.back.value = '';
        renderBoard();
      } catch (e) { show(Board.msg, '送出失敗：' + e.message, false); }
    };
    const set = el('button', { type: 'button', text: '貼上布告' });
    set.addEventListener('click', () => {
      const t = Board.input.value.trim();
      if (!t) { show(Board.msg, '沒有內容；要拿掉布告請按「清空」', false); return; }
      put(t, Board.back.value.trim());
    });
    const clr = el('button', { type: 'button', text: '清空（我回來了）' });
    clr.addEventListener('click', () => put('', ''));
    box.replaceChildren(el('div', { class: 'card board' }, Board.now,
      el('div', { class: 'board-form' }, Board.input, Board.back, el('div', {}, set, ' ', clr)), Board.msg));
    Board.built = true;
  }
  const b = S.board;
  Board.now.replaceChildren(b
    ? el('div', {}, el('b', { text: b.text }), el('div', { class: 'mut', text: '貼於 ' + (b.at || '?') + (b.back ? '；預計回來：' + b.back : '') }))
    : el('div', { class: 'mut', text: '布告欄是空的。' }));
}

// ---------- refresh loop ----------

function renderAll() {
  const y = window.scrollY;
  renderHeader();
  renderBoard();
  renderAsks();
  renderTree();
  renderMachine();
  renderRelay();
  // hook for map.js (the floor-plan view): it reads S.tree and redraws itself; absent = list only
  if (typeof mapOnRender === 'function') mapOnRender();
  window.scrollTo(0, y);
}

async function refresh() {
  if (S.refreshing) return;
  S.refreshing = true;
  try {
    const [tr, as, rl, bd] = await Promise.allSettled([api('/api/tree'), api('/api/asks'), api('/api/relay'), api('/api/board')]);
    const fails = [];
    if (tr.status === 'fulfilled') {
      if (tr.value.tree) S.tree = tr.value.tree; // keep the old table if this read had none
      S.treeErr = tr.value.error || null;
    } else fails.push('全景表 ' + tr.reason.message);
    if (as.status === 'fulfilled') S.asks = as.value.asks || []; else fails.push('等你的信 ' + as.reason.message);
    if (rl.status === 'fulfilled') S.relay = rl.value.letters || []; else fails.push('隊伍回覆 ' + rl.reason.message);
    if (bd.status === 'fulfilled') S.board = bd.value.user || null;
    S.failMsg = fails.length ? fails.join('；') : null;
    renderAll();
  } finally {
    S.refreshing = false;
  }
}

async function start() {
  try { await getSession(); } catch (e) { S.failMsg = e.message; tickFresh(); }
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && Panel.name) closePanel(); });
  await refresh();
  loadAnswered();
  route();
  setInterval(refresh, POLL_MS);
  setInterval(tickFresh, 1000);
}

start();
