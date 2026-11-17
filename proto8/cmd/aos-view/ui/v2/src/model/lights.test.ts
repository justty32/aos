// Light tests distinguish own status, descendants, whole rooms, and missing rollup counts.
import { test } from "node:test";
import assert from "node:assert/strict";
import type { Node } from "../api/types.ts";
import { belowOf, roomOf } from "./lights.ts";
import { treeRows } from "./tree.ts";
import { itemLight, layoutMap } from "./layoutMap.ts";

const lead = { id: "lead", kind: "agent", light: "green", children: ["child"], asks: 0,
  rollup: { worst: "red", counts: { red: 1, blue: 0, yellow: 0 }, nodes: 2, path: [] } } as Node;
const child = { ...lead, id: "child", children: [], parent: "lead", light: "red" } as Node;

test("below subtracts only the node's own light and chooses red before blue before yellow", () => {
  assert.deepEqual(belowOf(lead), { red: 1, blue: 0, yellow: 0, worst: "red" });
  assert.deepEqual(belowOf(child), { red: 0, blue: 0, yellow: 0, worst: null });
  const n = { ...lead, light: "blue" as const, rollup: { ...lead.rollup, counts: { red: 0, blue: 2, yellow: 3 } } };
  assert.deepEqual(belowOf(n), { red: 0, blue: 1, yellow: 3, worst: "blue" });
  assert.equal(belowOf({ ...n, rollup: { ...n.rollup, counts: { red: 0, blue: 1, yellow: 3 } } }).worst, "yellow");
});

test("missing counts show an unnumbered warning only when below is worse than self", () => {
  const n = { ...lead, rollup: { ...lead.rollup, counts: undefined } };
  assert.deepEqual(belowOf(n), { red: 0, blue: 0, yellow: 0, worst: "red" });
  assert.equal(belowOf({ ...n, light: "red" }).worst, null);
  assert.equal(belowOf({ ...n, rollup: { ...n.rollup, worst: "gray" } }).worst, null);
});

test("rooms include their lead and machine-room counts", () => {
  assert.equal(roomOf(child).red, 1);
  assert.equal(roomOf({ rollup: { worst: "yellow" } }).worst, "yellow");
  assert.equal(roomOf({ rollup: { worst: "green", counts: { red: 0, blue: 0, yellow: 0 } } }).worst, null);
});

test("tree rows and map items keep own lights regardless of folds", () => {
  const tree = { format: "test", generated_at: 0, roots: ["lead"], llm_workers: 0, nodes: { lead, child } };
  for (const open of [new Set<string>(), new Set(["lead"])]) {
    const row = treeRows(tree, open)[0];
    assert.equal(row.light, "green");
    assert.equal(row.below.red, 1);
  }
  for (const f of [{ all: "open" as const, ids: {} }, { all: "fold" as const, ids: {} }]) {
    for (const item of layoutMap(tree, null, 800, 800, f).items.filter((x) => x.id === "lead")) assert.equal(itemLight(tree, item), "green");
  }
});

test("deptsUnder selects departments, with the requested department first", async () => {
  const { deptsUnder } = await import("./tree.ts");
  const branch = { ...lead, id: "branch", children: ["leaf"] };
  const leaf = { ...child, id: "leaf", children: [] };
  const t = { format: "test", generated_at: 0, roots: ["lead"], llm_workers: 0,
    nodes: { lead: { ...lead, children: ["branch", "child"] }, branch, child, leaf } };
  assert.deepEqual(deptsUnder(t, "lead"), ["lead", "branch"]);
  assert.deepEqual(deptsUnder(t, "branch"), ["branch"]);
  assert.deepEqual(deptsUnder(t, "child"), []);
});
