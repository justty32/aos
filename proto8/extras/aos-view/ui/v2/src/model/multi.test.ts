// Selection tests cover toggles, both range directions, rectangle overlap, and normalization.
import { test } from "node:test";
import assert from "node:assert/strict";
import { bandRect, toggle, range, hits, norm } from "./multi.ts";
import type { MapItem } from "./layoutMap.ts";

test("band coordinates support every drag direction and scrolled origins", () => {
  assert.deepEqual(bandRect(100, 100, 40, 20, 10, -30), { x: 30, y: 50, w: 60, h: 80 });
  assert.deepEqual(bandRect(40, 20, 100, 100, 10, -30), { x: 30, y: 50, w: 60, h: 80 });
});
test("toggle adds and removes ids without mutating its input", () => {
  const list = ["a", "b"];
  assert.deepEqual(toggle(list, "b"), ["a"]);
  assert.deepEqual(toggle(list, "c"), ["a", "b", "c"]);
  assert.deepEqual(list, ["a", "b"]);
});
test("range accepts reverse anchors and missing anchors", () => {
  assert.deepEqual(range(["a", "b", "c", "d"], "a", "d"), ["a", "b", "c", "d"]);
  assert.deepEqual(range(["a", "b", "c", "d"], "d", "b"), ["b", "c", "d"]);
  assert.deepEqual(range(["a", "b"], "gone", "b"), ["b"]);
  assert.deepEqual(range(["a", "b"], null, "b"), ["b"]);
});
test("hits includes touching plates and dots but not rooms or folds", () => {
  const items = [{ kind: "plate", id: "a", x: 0, y: 0, w: 10, h: 10 }, { kind: "dot", id: "b", x: 10, y: 10, w: 5, h: 5 },
    { kind: "room", id: "room", x: 0, y: 0, w: 50, h: 50 }, { kind: "fold", id: "fold", x: 0, y: 0, w: 10, h: 10 },
    { kind: "plate", id: "far", x: 100, y: 100, w: 10, h: 10 }] as MapItem[];
  assert.deepEqual(hits(items, { x: 5, y: 5, w: 5, h: 5 }), ["a", "b"]);
  assert.deepEqual(hits(items, { x: 60, y: 60, w: 5, h: 5 }), []);
});
test("norm stores only genuine multi-selections", () => {
  assert.deepEqual(norm([]), []);
  assert.deepEqual(norm(["a"]), []);
  assert.deepEqual(norm(["a", "a"]), []);
  assert.deepEqual(norm(["a", "b", "a"]), ["a", "b"]);
});
