// Regression tests retain bottom-follow through a 48px layout shift and respect upward user scrolling.
import { test } from "node:test";
import assert from "node:assert/strict";
import { followsLayout } from "./historyScroll.ts";

test("a scroll event delivered before ResizeObserver does not cancel bottom-follow", () => {
  const previous = { top: 2283, client: 579, height: 2862 };
  const afterClamp = { top: 2283, client: 579, height: 2910 };
  assert.equal(followsLayout(previous, afterClamp, true), true);
  assert.equal(followsLayout(previous, { ...afterClamp, client: 531 }, true), true);
});
test("user scrolling up cancels following, even during a layout change", () => {
  const previous = { top: 2283, client: 579, height: 2862 };
  assert.equal(followsLayout(previous, { ...previous, top: 2000 }, true), false);
  assert.equal(followsLayout(previous, { top: 2000, client: 579, height: 2910 }, true), false);
  assert.equal(followsLayout(previous, { top: 2283, client: 579, height: 2910 }, false), false);
  assert.equal(followsLayout(null, previous, true), false);
});
