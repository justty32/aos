// Tests cover LRU capacity, access order, replacement, and expiration.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createMemo } from "./memo.ts";

test("expansion memo evicts the oldest of 201 entries", () => {
  const m = createMemo<boolean>(200);
  for (let i = 0; i < 201; i++) m.set(String(i), true, 0);
  assert.equal(m.get("0", 0), undefined);
  assert.equal(m.get("1", 0), true);
  assert.equal(m.get("200", 0), true);
});

test("history memo keeps eight agents and refreshes access order", () => {
  const m = createMemo<number>(8, 600);
  for (let i = 0; i < 8; i++) m.set(String(i), i, 0);
  assert.equal(m.get("0", 1), 0);
  m.set("8", 8, 1);
  assert.equal(m.get("1", 1), undefined);
  assert.equal(m.get("0", 599), 0);
  assert.equal(m.get("0", 601), undefined);
  assert.equal(m.get("8", 601), undefined);
});

test("set replaces an entry without evicting a different entry", () => {
  const m = createMemo<number>(2, 10);
  m.set("a", 1, 0);
  m.set("b", 2, 0);
  m.set("a", 3, 5);
  assert.equal(m.get("a", 10), 3);
  assert.equal(m.get("b", 10), undefined);
  assert.equal(m.get("a", 15), undefined);
});

test("zero capacity stores nothing and non-expiring memo survives time", () => {
  const empty = createMemo<boolean>(0);
  empty.set("a", true, 0);
  assert.equal(empty.get("a", 0), undefined);
  const m = createMemo<boolean>(1);
  m.set("a", false, 0);
  assert.equal(m.get("a", 1e9), false);
});
