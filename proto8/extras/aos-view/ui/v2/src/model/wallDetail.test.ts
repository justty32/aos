// Wall detail tests cover parsing, stepping, cycling, overrides, machine limits, and stale ids.
import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT, parseDetail, levelOf, step, cycle, setAll, setOne, prune } from "./wallDetail.ts";

test("parseDetail defaults malformed data and checks each stored field", () => {
  for (const raw of [null, "{", "null", "false", "42", '"detail"']) assert.deepEqual(parseDetail(raw), DEFAULT);
  assert.deepEqual(parseDetail('{"all":"bad","ids":{"a":"detail","b":"bad","c":2}}'), { all: "simple", ids: { a: "detail" } });
  assert.deepEqual(parseDetail('{"all":"fold","ids":[]}'), { all: "fold", ids: {} });
  assert.deepEqual(parseDetail('{"all":"detail","ids":{"a":"simple"}}'), { all: "detail", ids: { a: "simple" } });
});

test("step stops at detail, or simple for the machine room", () => {
  assert.equal(step("fold"), "simple");
  assert.equal(step("simple"), "detail");
  assert.equal(step("detail"), "detail");
  assert.equal(step("fold", "simple"), "simple");
  assert.equal(step("simple", "simple"), "simple");
  assert.equal(step("detail", "simple"), "simple");
});

test("cycle walks three levels and the machine room's two levels", () => {
  assert.equal(cycle("fold"), "simple");
  assert.equal(cycle("simple"), "detail");
  assert.equal(cycle("detail"), "fold");
  assert.equal(cycle("fold", "simple"), "simple");
  assert.equal(cycle("simple", "simple"), "fold");
});

test("node overrides win, whole-wall settings clear overrides, and machines clamp at simple", () => {
  const d = setOne(DEFAULT, "a", "fold");
  assert.equal(levelOf(d, "a"), "fold");
  assert.equal(levelOf(d, "b"), "simple");
  const all = setAll(d, "detail");
  assert.deepEqual(all, { all: "detail", ids: {} });
  assert.equal(levelOf(all, "a"), "detail");
  assert.equal(levelOf(all, "_machine", "simple"), "simple");
  assert.deepEqual(DEFAULT, { all: "simple", ids: {} });
});

test("prune removes only dead ids above 200 overrides", () => {
  const ids = Object.fromEntries(Array.from({ length: 201 }, (_, i) => [String(i), "fold" as const]));
  const d = { all: "simple" as const, ids };
  assert.deepEqual(prune(d, (id) => id === "100"), { all: "simple", ids: { "100": "fold" } });
  assert.equal(Object.keys(d.ids).length, 201);
  const small = { ...d, ids: { a: "fold" as const } };
  assert.equal(prune(small, () => false), small);
});
