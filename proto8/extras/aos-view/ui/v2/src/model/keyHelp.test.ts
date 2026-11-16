// The help reference must keep all eight areas and nonempty shortcut descriptions.
import { test } from "node:test";
import assert from "node:assert/strict";
import { KEY_HELP } from "./keyHelp.ts";

test("help has eight named areas and no empty shortcut or description", () => {
  assert.equal(KEY_HELP.length, 8);
  assert.equal(new Set(KEY_HELP.map((x) => x.area)).size, 8);
  for (const { area, rows } of KEY_HELP) {
    assert.ok(area.trim());
    assert.ok(rows.length);
    for (const [keys, what] of rows) { assert.ok(keys.trim()); assert.ok(what.trim()); }
  }
});
