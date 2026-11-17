// Map option tests verify safe parsing, plate sizes, and layout propagation.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_OPTS, parseOpts, plateOf } from "./mapOpts.ts";
import { layoutMap } from "./layoutMap.ts";
import type { Node, Tree } from "../api/types.ts";

test("map options check every field and default malformed input", () => {
  for (const raw of [null, "{", "false", "42", "null"]) assert.deepEqual(parseOpts(raw), DEFAULT_OPTS);
  assert.deepEqual(parseOpts('{"w":"fit","name":"full","over":"wrap","font":"l"}'), { w: "fit", name: "full", over: "wrap", font: "l" });
  assert.deepEqual(parseOpts('{"w":"wrong","font":"s","name":2,"over":"wrong"}'), { ...DEFAULT_OPTS, font: "s" });
});

test("plate width and wrapping obey options and fitted limits", () => {
  assert.deepEqual(plateOf(DEFAULT_OPTS, 200), { w: 116, h: 28 });
  assert.deepEqual(plateOf({ ...DEFAULT_OPTS, w: "wide", over: "wrap" }, 0), { w: 160, h: 44 });
  assert.equal(plateOf({ ...DEFAULT_OPTS, w: "xwide" }, 0).w, 220);
  assert.equal(plateOf({ ...DEFAULT_OPTS, w: "fit" }, 12).w, 116);
  assert.equal(plateOf({ ...DEFAULT_OPTS, w: "fit" }, 180).w, 180);
  assert.equal(plateOf({ ...DEFAULT_OPTS, w: "fit" }, 900).w, 280);
});

test("layout propagates custom plate dimensions and full names through rooms", () => {
  const make = (id: string, children: string[] = [], parent: string | null = null) => ({ id, kind: "agent", children, parent, light: "green", asks: 0, board: null, rollup: { nodes: 3, worst: "green" } }) as Node;
  const tree: Tree = { format: "test", generated_at: 0, roots: ["boss"], llm_workers: 0, nodes: {
    boss: make("boss", ["boss-team", "boss-worker"]), "boss-team": make("boss-team", ["boss-team-worker"], "boss"),
    "boss-worker": make("boss-worker", [], "boss"), "boss-team-worker": make("boss-team-worker", [], "boss-team"),
  } };
  for (const all of ["open", "fold"] as const) {
    const map = layoutMap(tree, null, 600, 1000, { all, ids: {} }, { w: 160, h: 44 }, true);
    for (const it of map.items) {
      assert.ok(it.x + it.w <= 600);
      if (it.kind === "plate" || it.kind === "fold") { assert.equal(it.w, 160); assert.equal(it.h, 44); assert.equal(it.name, it.id); }
    }
  }
});
