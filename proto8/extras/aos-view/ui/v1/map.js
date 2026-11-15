// 全景頁 phase 0b map: zoomable / pannable 2D floor plan of the agent tree (zero dependencies).
//
// Loaded after app.js and uses its globals (S, el, ICON, LIGHT_WORD, ago, Panel, $).
// app.js calls mapOnRender() at the end of renderAll(); that is the only hook.
//
// Pieces:
//   Layout   built once per tree shape: every node is a box at fixed world coordinates.
//            A node with children is a room: slot 0 is its lead desk (the head itself), then the
//            children in a stable order (first seen, new ones appended; kept in localStorage).
//            Proc roots and the llm worker count sit in a separate 機房 room.
//   View     #map-world holds the boxes and is moved/scaled with one CSS transform; each box's
//            content layer is counter-scaled so text stays at screen size. #map-pins (SVG, screen
//            coordinates) only draws the blue pins for asks.
//   Zoom     semantic, by the box's OWN on-screen width w, same rule at every depth:
//            w<24 dot · 24-120 light+name · 120-320 summary + child dots · >=320 room shows its
//            children (each applying the same rule) / leaf shows "Now".
//   Render   only boxes inside the viewport whose parent room is expanded; rAF throttled.
//   Input    wheel = zoom at cursor, drag = pan, click room = fly to it, click agent = side panel
//            (sets #agent=NAME, handled by app.js), 全覽 = fit all, Esc / 上一層 = out one level.
'use strict';

const MAP = {
  LW: 180, LH: 110, GAP: 24, PAD: 24, HEAD: 44, TOP_GAP: 80,
  DOT: 24, NAME: 120, EXPAND: 320,
  VIEW_KEY: 'aosview.view', ORDER_KEY: 'aosview.mapOrder',
};
const SEV = { red: 4, blue: 3, yellow: 2, green: 1, gray: 0 };

const M = {
  boxes: new Map(), sig: null, order: mapLoadOrder(),
  s: 1, tx: 0, ty: 0, fitted: false, focus: null,
  raf: 0, anim: 0, drag: null, vis: new Map(),
};

function mapLoadOrder() {
  try { return JSON.parse(localStorage.getItem(MAP.ORDER_KEY) || '{}') || {}; } catch (e) { return {}; }
}
function mapSaveOrder() {
  try { localStorage.setItem(MAP.ORDER_KEY, JSON.stringify(M.order)); } catch (e) { /* private mode */ }
}
function mapOn() { return document.body.classList.contains('map-mode'); }

// ---------- layout ----------

// stable child order for one room: keep the old order, drop ids that left, append new ones by name
function mapOrdered(roomKey, ids) {
  const old = M.order[roomKey] || [];
  const want = new Set(ids);
  const kept = old.filter((id) => want.has(id));
  const fresh = ids.filter((id) => !kept.includes(id)).sort();
  const res = kept.concat(fresh);
  if (res.length !== old.length || res.some((id, i) => id !== old[i])) { M.order[roomKey] = res; M.dirtyOrder = true; }
  return res;
}

function mapWorst(lights) {
  let w = 'gray';
  for (const l of lights) if ((SEV[l] || 0) > SEV[w]) w = l;
  return w;
}

// boxes: key -> {key, id, kind: 'top'|'room'|'machine'|'leaf'|'lead'|'llm', parent, items, x, y, w, h, head}
function mapBuild(t) {
  const boxes = new Map();
  const nodes = t.nodes || {};
  const seen = new Set();
  const add = (b) => { boxes.set(b.key, b); return b.key; };
  const visit = (id, parent) => {
    const n = nodes[id];
    if (!n || seen.has(id)) return null; // bad data loops / duplicates
    seen.add(id);
    const kids = (n.children || []).filter((c) => nodes[c] && !seen.has(c));
    if (!kids.length) return add({ key: id, id, kind: 'leaf', parent });
    const b = { key: id, id, kind: 'room', parent, items: [] };
    add(b);
    b.items.push(add({ key: '@lead:' + id, id, kind: 'lead', parent: id }));
    for (const c of mapOrdered(id, kids)) { const k = visit(c, id); if (k) b.items.push(k); }
    return id;
  };
  const top = { key: '__top', kind: 'top', parent: null, items: [] };
  add(top);
  const roots = (t.roots || []).filter((id) => nodes[id]);
  for (const id of mapOrdered('__top', roots.filter((id) => nodes[id].kind === 'agent'))) {
    const k = visit(id, '__top'); if (k) top.items.push(k);
  }
  const mach = { key: '__machine', kind: 'machine', parent: '__top', items: [] };
  add(mach);
  for (const id of mapOrdered('__machine', roots.filter((id) => nodes[id].kind !== 'agent'))) {
    const k = visit(id, '__machine'); if (k) mach.items.push(k);
  }
  mach.items.push(add({ key: '__llm', kind: 'llm', parent: '__machine' }));
  top.items.push('__machine');
  if (M.dirtyOrder) { M.dirtyOrder = false; mapSaveOrder(); }
  return boxes;
}

// sizes bottom-up, then absolute positions top-down; rows of ceil(sqrt(n)) items
function mapMeasure(boxes, key) {
  const b = boxes.get(key);
  if (!b.items) { b.w = MAP.LW; b.h = MAP.LH; return; }
  const gap = b.kind === 'top' ? MAP.TOP_GAP : MAP.GAP;
  for (const k of b.items) mapMeasure(boxes, k);
  const cols = Math.max(1, Math.ceil(Math.sqrt(b.items.length)));
  let y = 0, maxW = 0;
  b.rel = [];
  for (let i = 0; i < b.items.length; i += cols) {
    const row = b.items.slice(i, i + cols).map((k) => boxes.get(k));
    let x = 0, rowH = 0;
    for (const c of row) { b.rel.push([c.key, x, y]); x += c.w + gap; rowH = Math.max(rowH, c.h); }
    maxW = Math.max(maxW, x - gap);
    y += rowH + gap;
  }
  const contentH = Math.max(0, y - gap);
  if (b.kind === 'top') { b.head = 0; b.pad = 0; } else {
    b.pad = MAP.PAD;
    // the title bar grows with the room so it is still ~30px tall when the room opens at 320px
    b.head = Math.max(MAP.HEAD, Math.round((maxW + 2 * b.pad) * 0.1));
  }
  b.w = maxW + 2 * b.pad;
  b.h = b.head + contentH + 2 * b.pad;
}

function mapPlace(boxes, key, x, y) {
  const b = boxes.get(key);
  b.x = x; b.y = y;
  for (const [k, rx, ry] of b.rel || []) mapPlace(boxes, k, x + b.pad + rx, y + b.head + b.pad + ry);
}

function mapLayout() {
  const t = S.tree;
  if (!t) return false;
  const boxes = mapBuild(t);
  const sig = [...boxes.values()].map((b) => b.key + ':' + (b.items || []).join(',')).join('|');
  if (sig === M.sig) return false; // same shape: keep the old coordinates
  mapMeasure(boxes, '__top');
  mapPlace(boxes, '__top', 0, 0);
  M.boxes = boxes;
  M.sig = sig;
  if (M.focus && !boxes.has(M.focus)) M.focus = null;
  return true;
}

// ---------- view math ----------

function mapSize() { const v = $('#map'); return [v.clientWidth || 1, v.clientHeight || 1]; }

function mapFitRect(b) {
  const [vw, vh] = mapSize();
  const pad = 24;
  const s = Math.min((vw - 2 * pad) / b.w, (vh - 2 * pad) / b.h);
  return { s, tx: vw / 2 - (b.x + b.w / 2) * s, ty: vh / 2 - (b.y + b.h / 2) * s };
}

function mapClampS(s) { return Math.min(12, Math.max(0.002, s)); }

function mapFly(key) {
  const b = M.boxes.get(key);
  if (!b) return;
  M.focus = b.kind === 'top' ? null : key;
  const to = mapFitRect(b);
  const from = { s: M.s, tx: M.tx, ty: M.ty };
  const [vw, vh] = mapSize();
  // interpolate the world point at the screen centre and log(scale), so the zoom feels even
  const c0 = [(vw / 2 - from.tx) / from.s, (vh / 2 - from.ty) / from.s];
  const c1 = [(vw / 2 - to.tx) / to.s, (vh / 2 - to.ty) / to.s];
  const t0 = performance.now(), dur = 380;
  cancelAnimationFrame(M.anim);
  const step = () => {
    const k = Math.min(1, (performance.now() - t0) / dur);
    const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    M.s = Math.exp(Math.log(from.s) + (Math.log(to.s) - Math.log(from.s)) * e);
    const cx = c0[0] + (c1[0] - c0[0]) * e, cy = c0[1] + (c1[1] - c0[1]) * e;
    M.tx = vw / 2 - cx * M.s; M.ty = vh / 2 - cy * M.s;
    mapRenderNow();
    if (k < 1) M.anim = requestAnimationFrame(step); else M.anim = 0;
  };
  M.anim = requestAnimationFrame(step);
}

function mapFitAll(instant) {
  if (!M.boxes.has('__top')) return;
  if (instant) { Object.assign(M, mapFitRect(M.boxes.get('__top'))); M.focus = null; mapSchedule(); } else mapFly('__top');
  M.fitted = true;
}

function mapUp() {
  if (!M.focus) { mapFitAll(); return; }
  const b = M.boxes.get(M.focus);
  const p = b && b.parent;
  if (!p || p === '__top') mapFitAll(); else mapFly(p);
}

function mapZoomAt(mx, my, f) {
  const s = mapClampS(M.s * f);
  M.tx = mx - (mx - M.tx) * (s / M.s);
  M.ty = my - (my - M.ty) * (s / M.s);
  M.s = s;
  mapSchedule();
}

// ---------- render ----------

function mapSchedule() { if (!M.raf) M.raf = requestAnimationFrame(() => { M.raf = 0; mapRenderNow(); }); }

function mapNode(b) { return b.id ? S.tree.nodes[b.id] : null; }

function mapLight(b) {
  const n = mapNode(b);
  if (b.kind === 'room') return (n.rollup && n.rollup.worst) || n.light;
  if (b.kind === 'machine') return mapWorst(b.items.map((k) => mapLight(M.boxes.get(k))));
  if (b.kind === 'llm') return S.tree.llm_workers ? 'green' : 'gray';
  return n.light;
}

function mapName(b) {
  if (b.kind === 'machine') return '⚙️ 機房';
  if (b.kind === 'llm') return '🧠 llm 單次工作';
  if (b.kind === 'lead') return b.id + '（主管）';
  return b.id;
}

function mapCount(b) {
  if (b.kind === 'room') { const r = mapNode(b).rollup; return r ? r.nodes - 1 : b.items.length - 1; }
  if (b.kind === 'machine') return b.items.length - 1;
  return 0;
}

function mapTitle(b, big) {
  const n = mapNode(b);
  const light = mapLight(b);
  const isRoom = b.kind === 'room' || b.kind === 'machine';
  return el('div', { class: 'mt' },
    el('span', { title: LIGHT_WORD[light] || '', text: ICON[light] || '⚪' }),
    el('b', { text: mapName(b) }),
    isRoom ? el('span', { class: 'mut', text: '+' + mapCount(b) }) : null,
    n && n.asks ? el('span', { class: 'tag blue', text: '等你 ' + n.asks }) : null,
    b.kind === 'llm' ? el('span', { text: (S.tree.llm_workers || 0) + ' 個' }) : null,
    big && n && n.why ? el('span', { class: 'why light-' + n.light, text: n.why }) : null);
}

function mapContent(b, w, h) {
  const n = mapNode(b);
  const light = mapLight(b);
  const isRoom = b.kind === 'room' || b.kind === 'machine';
  if (w < MAP.DOT) {
    const d = Math.max(3, Math.min(14, Math.min(w, h) * 0.7));
    const dot = el('span', { class: 'mdot l-' + light });
    dot.style.width = dot.style.height = d + 'px';
    return [dot];
  }
  if (w < MAP.NAME) return [mapTitle(b, false)];
  if (isRoom && w >= MAP.EXPAND) {
    // opened room: title bar in its head band, the children draw themselves on top
    const bar = el('div', { class: 'mhead' }, mapTitle(b, true));
    bar.style.height = Math.max(18, b.head * M.s) + 'px';
    return [bar];
  }
  const out = [mapTitle(b, false)];
  if (n && n.why) out.push(el('div', { class: 'why light-' + n.light, text: n.why }));
  if (b.kind === 'llm') out.push(el('div', { class: 'mut', text: '跑完就結束的腦呼叫，只算個數' }));
  if (isRoom) {
    if (n && n.last_answer) out.push(el('div', { class: 'mline mut', text: '💬 ' + n.last_answer }));
    out.push(el('div', { class: 'mdots' }, b.items.map((k) => {
      const c = M.boxes.get(k);
      return el('span', { class: 'mdot l-' + mapLight(c), title: mapName(c) });
    })));
    return out;
  }
  if (w < MAP.EXPAND) {
    if (n && n.last_answer) out.push(el('div', { class: 'mline mut', text: '💬 ' + n.last_answer }));
    return out;
  }
  if (n) { // leaf / lead desk, big: "Now"
    out.push(el('div', { class: 'mnow' }, [
      '狀態 ' + (n.busy || n.state || '?'),
      '排隊 ' + (n.queued == null ? '-' : n.queued),
      '動靜 ' + ago(n.active_at),
    ].join(' · ')));
    if (n.last_answer) out.push(el('div', { class: 'mline2 mut', title: n.last_answer, text: '💬 最後一句：' + n.last_answer }));
    const rep = (n.reports || [])[0];
    if (rep) out.push(el('div', { class: 'mline mut', text: '📮 ' + (rep.title || '') + ' · ' + ago(rep.sent_at) }));
    if (n.kind === 'agent') out.push(el('div', { class: 'mut', text: '點一下看細節、說話、寄信' }));
  }
  return out;
}

function mapBox(b, sw, sh) {
  const outer = el('div', { class: 'mb' });
  outer.dataset.key = b.key;
  outer.style.left = b.x + 'px'; outer.style.top = b.y + 'px';
  outer.style.width = b.w + 'px'; outer.style.height = b.h + 'px';
  const kind = b.kind === 'machine' ? 'room' : b.kind;
  const inner = el('div', { class: 'mc k-' + kind + ' l-' + mapLight(b) + (sw < MAP.DOT ? ' tiny' : '') });
  inner.style.width = sw + 'px'; inner.style.height = sh + 'px';
  inner.style.transform = 'scale(' + (1 / M.s) + ')';
  inner.append(...mapContent(b, sw, sh));
  outer.append(inner);
  return outer;
}

function mapRenderNow() {
  if (!mapOn()) return;
  const world = $('#map-world');
  const [vw, vh] = mapSize();
  world.style.transform = 'translate(' + M.tx + 'px,' + M.ty + 'px) scale(' + M.s + ')';
  if (!S.tree || !M.boxes.has('__top')) {
    world.replaceChildren();
    $('#map-msg').textContent = S.tree ? '' : '還沒讀到 daemon 表。';
    return;
  }
  $('#map-msg').textContent = '';
  const out = [];
  M.vis = new Map();
  const walk = (key) => {
    const b = M.boxes.get(key);
    const sx = b.x * M.s + M.tx, sy = b.y * M.s + M.ty, sw = b.w * M.s, sh = b.h * M.s;
    if (sx > vw || sy > vh || sx + sw < 0 || sy + sh < 0) return; // off screen: skip it and its insides
    out.push(mapBox(b, sw, sh));
    M.vis.set(key, [sx, sy, sw, sh]);
    if (b.items && sw >= MAP.EXPAND) b.items.forEach(walk);
  };
  M.boxes.get('__top').items.forEach(walk);
  world.replaceChildren(...out);
  mapPins(vw, vh);
  mapCrumbs();
}

// blue pin (fixed screen size) on each node with asks; hidden nodes pin on the nearest visible ancestor
function mapPins(vw, vh) {
  const svg = $('#map-pins');
  svg.setAttribute('width', vw); svg.setAttribute('height', vh);
  const NS = 'http://www.w3.org/2000/svg';
  const count = new Map();
  for (const n of Object.values(S.tree.nodes || {})) {
    if (!n.asks) continue;
    let k = M.vis.has('@lead:' + n.id) ? '@lead:' + n.id : n.id;
    while (k && M.boxes.has(k) && !M.vis.has(k)) k = M.boxes.get(k).parent;
    if (k && M.vis.has(k)) count.set(k, (count.get(k) || 0) + n.asks);
  }
  const pins = [];
  for (const [k, c] of count) {
    const [sx, sy, sw] = M.vis.get(k);
    const cx = Math.min(vw - 12, Math.max(12, sx + sw - 2)), cy = Math.min(vh - 12, Math.max(12, sy + 2));
    const g = document.createElementNS(NS, 'g');
    g.setAttribute('class', 'pin');
    const circ = document.createElementNS(NS, 'circle');
    circ.setAttribute('cx', cx); circ.setAttribute('cy', cy); circ.setAttribute('r', 10);
    const tx = document.createElementNS(NS, 'text');
    tx.setAttribute('x', cx); tx.setAttribute('y', cy + 4); tx.setAttribute('text-anchor', 'middle');
    tx.textContent = String(c);
    g.append(circ, tx);
    pins.push(g);
  }
  svg.replaceChildren(...pins);
}

function mapCrumbs() {
  const chain = [];
  for (let k = M.focus; k && k !== '__top'; k = M.boxes.get(k) && M.boxes.get(k).parent) chain.unshift(k);
  const parts = [el('a', { href: '#', text: '全部', onclick: (e) => { e.preventDefault(); mapFitAll(); } })];
  for (const k of chain) {
    parts.push(' › ', el('a', { href: '#', text: mapName(M.boxes.get(k)), onclick: (e) => { e.preventDefault(); mapFly(k); } }));
  }
  $('#map-crumbs').replaceChildren(...parts);
}

// ---------- input ----------

function mapClick(x, y) {
  const hit = document.elementFromPoint(x, y);
  const box = hit && hit.closest('#map-world .mb');
  const b = box && M.boxes.get(box.dataset.key);
  if (!b) return;
  const n = mapNode(b);
  if ((b.kind === 'leaf' || b.kind === 'lead') && n && n.kind === 'agent') {
    location.hash = '#agent=' + encodeURIComponent(b.id); // app.js route() opens the side panel
    return;
  }
  mapFly(b.kind === 'lead' ? b.parent : b.key);
}

function mapWire() {
  const v = $('#map');
  v.addEventListener('wheel', (e) => {
    e.preventDefault();
    cancelAnimationFrame(M.anim); M.anim = 0;
    const r = v.getBoundingClientRect();
    const unit = e.deltaMode === 1 ? 0.05 : e.deltaMode === 2 ? 1 : 0.0015;
    mapZoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * unit));
  }, { passive: false });
  v.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    cancelAnimationFrame(M.anim); M.anim = 0;
    M.drag = { id: e.pointerId, x: e.clientX, y: e.clientY, tx: M.tx, ty: M.ty, moved: false };
    v.setPointerCapture(e.pointerId);
  });
  v.addEventListener('pointermove', (e) => {
    const d = M.drag;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (!d.moved && Math.abs(dx) + Math.abs(dy) > 4) { d.moved = true; v.classList.add('dragging'); }
    if (d.moved) { M.tx = d.tx + dx; M.ty = d.ty + dy; mapSchedule(); }
  });
  const end = (e, cancel) => {
    const d = M.drag;
    if (!d || d.id !== e.pointerId) return;
    M.drag = null;
    v.classList.remove('dragging');
    if (!d.moved && !cancel) mapClick(e.clientX, e.clientY);
  };
  v.addEventListener('pointerup', (e) => end(e, false));
  v.addEventListener('pointercancel', (e) => end(e, true));
  // capture phase on window runs before app.js's Escape handler: if the panel is open, let app.js close it
  window.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape' || !mapOn() || Panel.name) return;
    const a = document.activeElement;
    if (a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
    mapUp();
  }, true);
  window.addEventListener('resize', mapSchedule);
  $('#map-fit').addEventListener('click', () => mapFitAll());
  $('#map-up').addEventListener('click', mapUp);
  for (const b of document.querySelectorAll('#views button')) b.addEventListener('click', () => mapSetView(b.dataset.v));
}

function mapSetView(v) {
  const on = v === 'map';
  document.body.classList.toggle('map-mode', on);
  for (const b of document.querySelectorAll('#views button')) b.classList.toggle('on', b.dataset.v === (on ? 'map' : 'list'));
  try { localStorage.setItem(MAP.VIEW_KEY, on ? 'map' : 'list'); } catch (e) { /* private mode */ }
  if (on) { mapLayout(); if (!M.fitted) mapFitAll(true); mapSchedule(); }
}

// called by app.js renderAll() after every refresh
function mapOnRender() {
  mapLayout();
  if (!mapOn()) return;
  if (!M.fitted && M.boxes.has('__top')) mapFitAll(true);
  mapSchedule();
}

mapWire();
mapSetView((() => { try { return localStorage.getItem(MAP.VIEW_KEY); } catch (e) { return null; } })() || 'list');
