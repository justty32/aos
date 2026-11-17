// Canvas name tests use a fake measuring context to verify ellipses and font-sensitive caching.
import { test } from "node:test";
import assert from "node:assert/strict";
import { textW, fitName, widths } from "./mapText.ts";

test("text measurements cache by font and middle ellipses respect the available width", () => {
  const old = Object.getOwnPropertyDescriptor(globalThis, "document");
  let calls = 0;
  const ctx = { font: "", measureText(s: string) { calls++; return { width: s.length * parseInt(this.font) }; } };
  Object.defineProperty(globalThis, "document", { configurable: true, value: { createElement: () => ({ getContext: () => ctx }) } });
  try {
    widths.clear();
    assert.equal(textW("abcd", 12), 48);
    assert.equal(textW("abcd", 12), 48);
    assert.equal(calls, 1);
    assert.equal(textW("abcd", 15), 60);
    assert.equal(calls, 2);
    assert.equal(fitName("abc", 100, 12), "abc");
    const cut = fitName("abcdefghijk", 72, 12);
    assert.ok(cut.includes("…"));
    assert.ok(textW(cut, 12) <= 72);
  } finally {
    if (old) Object.defineProperty(globalThis, "document", old); else Reflect.deleteProperty(globalThis, "document");
  }
});
