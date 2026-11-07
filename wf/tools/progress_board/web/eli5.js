// This helper adds or updates plain-language boxes without replacing surrounding content.
"use strict";
window.AosEli5 = (() => {
  const boxes = new WeakMap(), ns = "http://www.w3.org/2000/svg";
  function set(parent, key, text, before = null) {
    if (!parent) return;
    let items = boxes.get(parent);
    if (!items) { items = new Map(); boxes.set(parent, items); }
    let box = items.get(key);
    const value = typeof text === "string" ? text.trim() : "";
    if ((!box && !value) || (box && box.lastChild.textContent === value)) return;
    const x = window.scrollX, y = window.scrollY;
    if (!value) { box.remove(); items.delete(key); }
    else if (box) box.lastChild.textContent = value;
    else {
      box = document.createElement("aside"); box.className = "eli5-box"; box.dataset.eli5 = key;
      const label = document.createElement("span"); label.className = "eli5-label";
      const bulb = document.createElementNS(ns, "svg");
      bulb.setAttribute("viewBox", "0 0 24 24"); bulb.setAttribute("aria-hidden", "true");
      const path = document.createElementNS(ns, "path");
      Object.entries({d: "M9 18h6 M10 21h4 M8 12a6 6 0 1 1 8 0c-1 1-1 2-1 3H9c0-1 0-2-1-3Z", fill: "none", stroke: "currentColor", "stroke-width": "1.6", "stroke-linecap": "round", "stroke-linejoin": "round"}).forEach(([name, value]) => path.setAttribute(name, value));
      bulb.append(path); label.append(bulb, document.createTextNode("白話"));
      const body = document.createElement("p"); body.textContent = value;
      box.append(label, body); items.set(key, box); parent.insertBefore(box, before);
    }
    window.scrollTo(x, y);
  }
  return {set};
})();
