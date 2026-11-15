import { test } from "node:test";
import assert from "node:assert/strict";
import { decide, normalize, isSubmit, type Binding, type KeyLike } from "./keys.ts";

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
