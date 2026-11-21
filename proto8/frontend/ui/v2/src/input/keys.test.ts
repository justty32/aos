// Tests for the keyboard layer (keys.ts): normalizing a key event, zones, input fields, and which binding wins.
import { test } from "node:test";
import assert from "node:assert/strict";
import { bind, decide, install, normalize, isSubmit, type Binding, type KeyLike } from "./keys.ts";

const k = (key: string, o: Partial<KeyLike> = {}): KeyLike => ({ key, ctrlKey: false, metaKey: false, altKey: false, shiftKey: false, ...o });
const hit: string[] = [];
const B: Binding[] = [
  { key: "mod+k", inInput: true, run: () => hit.push("search") },
  { key: "/", run: () => hit.push("slash") },
  { key: "j", zone: "stage", run: () => hit.push("stage-j") },
  { key: "j", zone: "inbox", run: () => hit.push("inbox-j") },
  { key: "alt+1", run: () => hit.push("f1") },
];

test("normalize: lower-case letters only; shift is its own key; alt+digit by code", () => {
  assert.equal(normalize(k("j")), "j");
  assert.equal(normalize(k("J", { shiftKey: true })), "shift+j");
  assert.equal(normalize(k("k", { ctrlKey: true })), "mod+k");
  assert.equal(normalize(k("¡", { altKey: true, code: "Digit1" })), "alt+1");
});

test("IME guard: nothing while composing (A6)", () => {
  assert.deepEqual(decide(k("Enter", { isComposing: true }), { inInput: true, zone: null, overlays: 1 }, B), { type: "none" });
  assert.deepEqual(decide(k("Escape", { keyCode: 229 }), { inInput: true, zone: null, overlays: 1 }, B), { type: "none" });
  assert.equal(isSubmit(k("Enter", { ctrlKey: true, isComposing: true })), false);
  assert.equal(isSubmit(k("Enter", { ctrlKey: true })), true);
  assert.equal(isSubmit(k("Enter")), false);
});

test("in an input: Esc only blurs, single keys are the input's, Ctrl+K still works", () => {
  const c = { inInput: true, zone: "inspector" as const, overlays: 2 };
  assert.deepEqual(decide(k("Escape"), c, B), { type: "blur" });
  assert.deepEqual(decide(k("/"), c, B), { type: "none" });
  assert.deepEqual(decide(k("j"), c, B), { type: "none" });
  const a = decide(k("k", { ctrlKey: true }), c, B);
  assert.equal(a.type === "run" && a.b.key, "mod+k");
});

test("outside inputs: zones pick the binding; Esc closes the top overlay first", () => {
  const s = decide(k("j"), { inInput: false, zone: null, overlays: 0 }, B);
  s.type === "run" && s.b.run();
  const i = decide(k("j"), { inInput: false, zone: "inbox", overlays: 0 }, B);
  i.type === "run" && i.b.run();
  assert.deepEqual(hit.slice(-2), ["stage-j", "inbox-j"]);
  assert.deepEqual(decide(k("j"), { inInput: false, zone: "inspector", overlays: 0 }, B), { type: "none" });
  assert.deepEqual(decide(k("J", { shiftKey: true }), { inInput: false, zone: null, overlays: 0 }, B), { type: "none" });
  assert.deepEqual(decide(k("Escape"), { inInput: false, zone: null, overlays: 1 }, B), { type: "overlay" });
  assert.equal(decide(k("¡", { altKey: true, code: "Digit1" }), { inInput: false, zone: "inbox", overlays: 0 }, B).type, "run");
});

test("Tab and Shift+Tab are distinct; CapsLock does not imply Shift", () => {
  const b: Binding[] = [{ key: "Tab", zone: "stage", run() {} }];
  const ctx = { inInput: false, zone: "stage" as const, overlays: 0 };
  assert.equal(normalize(k("Tab", { shiftKey: true })), "shift+Tab");
  assert.equal(decide(k("Tab"), ctx, b).type, "run");
  assert.equal(decide(k("Tab", { shiftKey: true }), ctx, b).type, "none");
  assert.equal(normalize(k("Q")), "q");
  assert.equal(normalize(k("q", { shiftKey: true })), "shift+q");
});

test("when false leaves native handling; true runs in the matching zone", () => {
  const ctx = { inInput: false, zone: "stage" as const, overlays: 0 };
  let focused = false;
  const b: Binding[] = [{ key: "Tab", zone: "stage", when: () => focused, run() {} }];
  assert.deepEqual(decide(k("Tab"), ctx, b), { type: "none" });
  focused = true;
  assert.equal(decide(k("Tab"), ctx, b).type, "run");
  assert.equal(decide(k("Tab"), { ...ctx, zone: "tree" }, b).type, "none");
  const input: Binding[] = [{ key: "mod+k", inInput: true, when: () => false, run() {} }];
  assert.equal(decide(k("k", { ctrlKey: true }), { ...ctx, inInput: true }, input).type, "none");
});

test("DOM dispatch does not preventDefault when a binding's when is false", () => {
  const oldWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const oldDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  let handler: (e: KeyboardEvent) => void;
  Object.defineProperty(globalThis, "window", { configurable: true, value: {
    addEventListener(_name: string, h: (e: KeyboardEvent) => void) { handler = h; }, removeEventListener() {},
  } });
  Object.defineProperty(globalThis, "document", { configurable: true, value: { activeElement: null } });
  let focused = false, prevented = 0, runs = 0;
  const offBind = bind([{ key: "Tab", zone: "stage", when: () => focused, run: () => runs++ }]);
  const offInstall = install();
  try {
    const event = { ...k("Tab"), preventDefault() { prevented++; } } as KeyboardEvent;
    handler!(event);
    assert.equal(prevented, 0);
    assert.equal(runs, 0);
    focused = true;
    handler!(event);
    assert.equal(prevented, 1);
    assert.equal(runs, 1);
  } finally {
    offInstall(); offBind();
    if (oldWindow) Object.defineProperty(globalThis, "window", oldWindow); else Reflect.deleteProperty(globalThis, "window");
    if (oldDocument) Object.defineProperty(globalThis, "document", oldDocument); else Reflect.deleteProperty(globalThis, "document");
  }
});

test("option numbers do not consume input text or Alt+number filters", () => {
  const b: Binding[] = [{ key: "2", run() {} }, { key: "alt+2", run() {} }, { key: "?", run() {} }];
  const ctx = { inInput: false, zone: "stage" as const, overlays: 0 };
  const a = decide(k("2"), ctx, b);
  assert.equal(a.type === "run" && a.b.key, "2");
  const filter = decide(k("2", { altKey: true, code: "Digit2" }), ctx, b);
  assert.equal(filter.type === "run" && filter.b.key, "alt+2");
  assert.equal(decide(k("2"), { ...ctx, inInput: true }, b).type, "none");
  assert.equal(decide(k("?", { shiftKey: true }), { ...ctx, inInput: true }, b).type, "none");
  assert.equal(normalize(k("?", { shiftKey: true })), "?");
});
