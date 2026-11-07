// This helper updates plain-language text and per-item freshness without replacing surrounding content.
"use strict";
window.AosEli5 = (() => {
  const boxes = new WeakMap(), ns = "http://www.w3.org/2000/svg";
  function set(parent, key, item, before = null) {
    if (!parent) return;
    let items = boxes.get(parent);
    if (!items) { items = new Map(); boxes.set(parent, items); }
    let box = items.get(key);
    if (box && box.parentNode !== parent) { items.delete(key); box = null; }
    const value = typeof item?.text === "string" ? item.text.trim() : "";
    const date = new Date(item?.updated_at);
    const time = item?.provided ? "各線自己寫的白話" : item?.updated_at && !Number.isNaN(+date) ? `白話更新於 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}` : "";
    const stale = Boolean(item?.stale && !item?.provided);
    const signature = JSON.stringify([value, time, stale]);
    if ((!box && !value) || box?.dataset.signature === signature) return;
    const x = window.scrollX, y = window.scrollY;
    if (!value) { box.remove(); items.delete(key); }
    else {
      if (!box) {
      box = document.createElement("aside"); box.className = "eli5-box"; box.dataset.eli5 = key;
      const label = document.createElement("span"); label.className = "eli5-label";
      const bulb = document.createElementNS(ns, "svg");
      bulb.setAttribute("viewBox", "0 0 24 24"); bulb.setAttribute("aria-hidden", "true");
      const path = document.createElementNS(ns, "path");
      Object.entries({d: "M9 18h6 M10 21h4 M8 12a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3Z", fill: "none", stroke: "currentColor", "stroke-width": "1.6", "stroke-linecap": "round", "stroke-linejoin": "round"}).forEach(([name, value]) => path.setAttribute(name, value));
      bulb.append(path); label.append(bulb, document.createTextNode("白話"));
      const body = document.createElement("p"), meta = document.createElement("div"); meta.className = "eli5-meta";
      const updated = document.createElement("span"), pending = document.createElement("span"); pending.className = "eli5-stale"; pending.textContent = "白話更新中";
      meta.append(updated, pending); box.append(label, body, meta); items.set(key, box); parent.insertBefore(box, before);
      }
      box.children[1].textContent = value;
      box.children[2].children[0].textContent = time;
      box.children[2].children[1].hidden = !stale;
      box.dataset.signature = signature;
    }
    window.scrollTo(x, y);
  }
  return {set};
})();
