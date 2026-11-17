// Keyboard (12.8 #4, Argon A5/A6/A9; written by opus, panels register only through here).
// - Every key goes through the IME guard first: while composing (注音 / 倉頡 picking a word) nothing is ours.
// - In an input: only Escape (= blur, never close or clear) and bindings marked inInput (Ctrl+K) work.
//   Ctrl+Enter is not here: each form handles its own, so it only acts on the form that has the caret.
// - Outside inputs: zones (tree / inbox = the to-do tab / stage / inspector), Tab moves between them; arrows and j/k act on the
//   zone that has focus (stage when none); the inspector keeps native scrolling.
// - Escape closes only the top layer (overlay stack), then clears the selection.

export type Zone = "tree" | "inbox" | "stage" | "inspector";
export interface KeyLike {
  key: string; ctrlKey: boolean; metaKey: boolean; altKey: boolean; shiftKey: boolean;
  isComposing?: boolean; keyCode?: number; code?: string;
}
export interface Binding { key: string; zone?: Zone | "global"; inInput?: boolean; when?: (e: KeyboardEvent) => boolean; run: () => void }
export interface Ctx { inInput: boolean; zone: Zone | null; overlays: number }
export type Action = { type: "none" } | { type: "blur" } | { type: "overlay" } | { type: "run"; b: Binding };

export function composing(e: KeyLike): boolean {
  return !!e.isComposing || e.keyCode === 229;
}

/** "mod+k", "alt+1", "shift+?", "j", "Enter", "Escape", "ArrowDown" ... (single letters lower-case only: J ≠ j). */
export function normalize(e: KeyLike): string {
  const parts: string[] = [];
  if (e.ctrlKey || e.metaKey) parts.push("mod");
  if (e.altKey) parts.push("alt");
  let k = e.key;
  if (e.altKey && e.code && /^Digit[0-9]$/.test(e.code)) k = e.code.slice(5);   // Alt+1 is "¡" on some layouts
  if ((k.length === 1 && /[a-z]/i.test(k)) || k === "Tab") {
    if (e.shiftKey) parts.push("shift");
    if (k !== "Tab") k = k.toLowerCase();
  }
  parts.push(k);
  return parts.join("+");
}

export function decide(e: KeyLike, ctx: Ctx, bindings: Binding[]): Action {
  if (composing(e)) return { type: "none" };
  const k = normalize(e);
  const allowed = (x: Binding) => !x.when || x.when(e as KeyboardEvent);
  if (ctx.inInput) {
    if (k === "Escape") return { type: "blur" };
    const b = bindings.find((x) => x.key === k && x.inInput && allowed(x));
    return b ? { type: "run", b } : { type: "none" };
  }
  if (k === "Escape" && ctx.overlays > 0) return { type: "overlay" };
  const zone = ctx.zone || "stage";
  const b = bindings.find((x) => x.key === k && (x.zone === zone) && allowed(x)) || bindings.find((x) => x.key === k && (!x.zone || x.zone === "global") && allowed(x));
  return b ? { type: "run", b } : { type: "none" };
}

// ---- DOM side ----
const bindings: Binding[] = [];
const overlays: (() => void)[] = [];

export function bind(list: Binding[]): () => void {
  bindings.push(...list);
  return () => { for (const b of list) { const i = bindings.indexOf(b); if (i >= 0) bindings.splice(i, 1); } };
}

/** an open layer (dialog, search, decision card): Esc closes the top one first. */
export function pushOverlay(close: () => void): () => void {
  overlays.push(close);
  return () => { const i = overlays.lastIndexOf(close); if (i >= 0) overlays.splice(i, 1); };
}

function isInput(el: Element | null): boolean {
  if (!el) return false;
  const t = el.tagName;
  return t === "INPUT" || t === "TEXTAREA" || t === "SELECT" || (el as HTMLElement).isContentEditable;
}

export function zoneOf(el: Element | null): Zone | null {
  const z = el?.closest?.("[data-zone]")?.getAttribute("data-zone");
  return z === "tree" || z === "inbox" || z === "stage" || z === "inspector" ? z : null;
}

export function install(): () => void {
  const h = (e: KeyboardEvent) => {
    const el = document.activeElement;
    const a = decide(e, { inInput: isInput(el), zone: zoneOf(el), overlays: overlays.length }, bindings);
    if (a.type === "none") return;
    if (a.type === "blur") { (el as HTMLElement).blur(); e.preventDefault(); return; }
    if (a.type === "overlay") { overlays[overlays.length - 1](); e.preventDefault(); return; }
    // arrows in the inspector keep native scrolling: the inspector binds no arrows
    a.b.run();
    e.preventDefault();
  };
  window.addEventListener("keydown", h);
  return () => window.removeEventListener("keydown", h);
}

/** for forms: Ctrl/Cmd+Enter, never while composing. */
export function isSubmit(e: KeyLike): boolean {
  return !composing(e) && e.key === "Enter" && (e.ctrlKey || e.metaKey);
}
