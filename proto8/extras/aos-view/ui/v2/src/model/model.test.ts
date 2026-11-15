import { test } from "node:test";
import assert from "node:assert/strict";
import { readBoard, boardCounts } from "./board.ts";
import { buildInbox, waitReason, WAIT } from "./inbox.ts";
import { chainOf, membersOf, standFor, soleRoot, leadOf, MACHINE } from "./tree.ts";
import { ago } from "./time.ts";
import { MemoryKv, loadDraft, saveDraft, listDrafts, pruneDrafts, emptyDraft, NONE } from "./drafts.ts";
import { parseHash, toHash } from "../state/route.ts";
import type { Node, OutItem, Tree } from "../api/types.ts";

const NOW = Date.parse("2026-11-14T06:30:00Z") / 1000;
const iso = (t: number) => new Date(t * 1000).toISOString();
function node(id: string, o: Partial<Node> = {}): Node {
  return { id, kind: "agent", state: "running", phase: "running", busy: null, queued: 0, reason: null, cooldown: null,
    light: "green", why: "ok", parent: null, parent_by: null, children: [], rollup: { worst: "green", why: "", nodes: 1, path: [id] },
    active_at: NOW - 60, last_answer: null, messages: 1, asks: 0, reports: [], tags: [], team: null, note: null, aide: null,
    passed: 0, team_light: null, board: null, ...o };
}
function tree(ns: Node[]): Tree {
  const nodes: Record<string, Node> = {};
  for (const n of ns) nodes[n.id] = n;
  for (const n of ns) if (n.parent && n.parent_by !== "aide") nodes[n.parent].children.push(n.id);
  return { format: "view-tree/0", generated_at: NOW, roots: ns.filter((n) => !n.parent).map((n) => n.id), llm_workers: 0, nodes };
}

test("board/1 four steps (06 §7.3)", () => {
  const b = { format: "board/1" as const, updated_at: iso(NOW - 60), mode: "dnd" as const,
    waiting_on: [{ who: "user", what: "pick", since_at: iso(NOW - 600) }] };
  assert.equal(readBoard(b, "running", NOW)!.mode, "dnd");
  assert.equal(readBoard({ ...b, format: undefined }, "running", NOW)!.mode, "dnd");
  assert.equal(readBoard(null, "running", NOW), null);
  const future = readBoard({ ...b, updated_at: iso(NOW + 3600) }, "running", NOW)!;
  assert.equal(future.clockOdd, true);
  const old = readBoard({ ...b, updated_at: iso(NOW - 25 * 3600) }, "running", NOW)!;
  assert.deepEqual([old.stale, old.mode, old.waiting.length], [true, "here", 0]);
  const exp = readBoard({ ...b, expires_at: iso(NOW - 1) }, "running", NOW)!;
  assert.equal(exp.stale, true);
  assert.equal(readBoard(b, "sleeping", NOW)!.mode, "away");
  assert.equal(readBoard({ ...b, back_at: iso(NOW - 5) }, "running", NOW)!.overdue, true);
  const c = boardCounts([node("a", { board: b }), node("b", { board: { ...b, mode: "busy", waiting_on: [] } }), node("c")], NOW);
  assert.deepEqual([c.dnd, c.waiting, c.waitingUser.map((w) => w.id)], [1, 1, ["a"]]);
});

test("tree: chain, members with the lead desk first, machine room", () => {
  const t = tree([node("boss"), node("boss-a", { parent: "boss" }), node("boss-a-x", { parent: "boss-a" }),
    node("LiteLLM", { kind: "external" })]);
  assert.deepEqual(chainOf(t, "boss-a-x"), ["boss", "boss-a", "boss-a-x"]);
  // one top department: the company view opens it (lead desk first), and its children stand in the company view
  assert.equal(soleRoot(t), "boss");
  assert.equal(leadOf(t, null), "boss");
  assert.deepEqual(membersOf(t, null), ["boss", "boss-a", MACHINE]);
  assert.equal(standFor(t, "boss-a"), null);
  assert.deepEqual(membersOf(t, "boss-a"), ["boss-a", "boss-a-x"]);
  assert.deepEqual(membersOf(t, MACHINE), ["LiteLLM"]);
  assert.equal(standFor(t, "boss-a-x"), "boss-a");
  assert.equal(standFor(t, "LiteLLM"), MACHINE);
  assert.deepEqual(chainOf(t, "LiteLLM"), [MACHINE, "LiteLLM"]);
});

test("waiting long thresholds (Q3 as recommended)", () => {
  const t = tree([node("a"), node("s", { state: "stopped" })]);
  const o = (x: Partial<OutItem>): OutItem => ({ letter: "L", batch: null, kind: "mail", to: "a", target: null, title: "t", what: "",
    status: null, sent_at: NOW - 60, delivery: "queued", queue_ahead: 0, checked_at: null, turn: null, reply: null, order: null,
    correction_of: null, gone: false, followed: true, ...x });
  assert.equal(waitReason(o({ to: "s" }), t, NOW), "對方停了，信沒人讀");
  assert.equal(waitReason(o({}), t, NOW), null);
  assert.equal(waitReason(o({ sent_at: NOW - WAIT.idle }), t, NOW), "對方閒著但沒讀");
  assert.equal(waitReason(o({ sent_at: NOW - WAIT.idle, turn: { queued: 2, busy: null, active_at: null }, queue_ahead: 1 }), t, NOW), null);
  assert.equal(waitReason(o({ sent_at: NOW - WAIT.turn, turn: { queued: 2, busy: null, active_at: null }, queue_ahead: 1 }), t, NOW),
    "對方這一輪還沒結束，前面還有 1 則");
  assert.equal(waitReason(o({ delivery: "read", sent_at: NOW - WAIT.read }), t, NOW), "讀了但沒回");
  assert.equal(waitReason(o({ delivery: "read", sent_at: NOW - WAIT.read, reply: { letter: "r", status: "DONE", title: "", at: NOW } }), t, NOW), null);
  assert.equal(waitReason(o({ gone: true }), t, NOW), "對方已經收隊，信沒人讀");
});

test("inbox: order, answered-here hidden, dismissed and seen", () => {
  const t = tree([node("a", { light: "red", why: "crashed: x" }), node("b")]);
  const asks = [{ letter: "q1", kind: "decide" as const, from: "a", title: "late", what: "", decide: null, questions: [], urgent: false,
    risk: "normal" as const, deadline: null, sent_at: NOW - 10, unseen: true, same: 0 },
    { letter: "q2", kind: "decide" as const, from: "b", title: "urgent", what: "", decide: null, questions: [], urgent: true,
      risk: "normal" as const, deadline: null, sent_at: NOW - 5, unseen: true, same: 0 }];
  const relay = [{ dir: "in" as const, kind: "mail" as const, letter: "r1", from: "b", to: "user", title: "hi", status: "DONE", what: "", sent_at: NOW - 30, in_reply_to: null }];
  const base = { tree: t, asks, relay, outbox: [], seen: {}, dismissed: {}, answeredHere: new Set<string>(), now: NOW };
  assert.deepEqual(buildInbox(base).map((x) => x.key), ["ask:q2", "ask:q1", "red:a:crashed: x", "in:r1"]);
  assert.deepEqual(buildInbox({ ...base, answeredHere: new Set(["q2"]), seen: { "in:r1": NOW }, dismissed: { "red:a:crashed: x": NOW } })
    .map((x) => x.key), ["ask:q1"]);
});

test("route: hash round trip", () => {
  const r = parseHash("#/boss/boss-a?sel=boss-a-x&tab=thread&ask=L.1");
  assert.deepEqual(r, { focus: "boss-a", sel: "boss-a-x", tab: "thread", view: "wall", ask: "L.1", q: 0 });
  assert.equal(toHash(r, ["boss", "boss-a"]), "#/boss/boss-a?sel=boss-a-x&tab=thread&ask=L.1");
  assert.deepEqual(parseHash("#/../<x>?sel=<b>&tab=evil"), { focus: null, sel: null, tab: "now", view: "wall", ask: null, q: 0 });
  assert.equal(parseHash("#/_machine").focus, "_machine");
});

test("drafts: one per target, all fields, prune", () => {
  const kv = new MemoryKv();
  const d = { ...emptyDraft(), text: "hello", mode: "mail" as const, mailTitle: "T", fields: { budget: "3" } };
  saveDraft(kv, "a", d, NOW);
  const back = loadDraft(kv, "a");
  assert.deepEqual([back.text, back.mode, back.mailTitle, back.fields.budget], ["hello", "mail", "T", "3"]);
  saveDraft(kv, null, { ...emptyDraft(), text: "no target yet" }, NOW);
  assert.equal(loadDraft(kv, null).text, "no target yet");
  saveDraft(kv, "a", emptyDraft(), NOW);           // empty = removed
  assert.equal(listDrafts(kv).map((x) => x.target).join(), NONE);
  saveDraft(kv, "gone", { ...emptyDraft(), text: "x" }, NOW);
  saveDraft(kv, "old", { ...emptyDraft(), text: "x" }, NOW - 15 * 86400);
  assert.equal(pruneDrafts(kv, NOW, (id) => id !== "gone"), 2);
  assert.deepEqual(listDrafts(kv).map((x) => x.target), [NONE]);
});

test("ago", () => {
  assert.equal(ago(NOW - 10, NOW), "剛剛");
  assert.equal(ago(NOW - 600, NOW), "10 分前");
  assert.equal(ago(null, NOW), "沒有紀錄");
});

test("tree rows (02f §2): order, closed sums, default open, short names", async () => {
  const { treeRows, defaultOpen, shortName, openFor } = await import("./tree.ts");
  const t = tree([
    node("boss", { rollup: { worst: "red", why: "x", nodes: 5, path: [] } }),
    node("boss-sol-1", { parent: "boss", light: "red", asks: 0 }),
    node("boss-team", { parent: "boss", rollup: { worst: "blue", why: "", nodes: 2, path: [] } }),
    node("boss-team-a", { parent: "boss-team", asks: 2, light: "blue" }),
    node("loner"),
    node("litellm", { kind: "external" }),
  ]);
  assert.deepEqual(defaultOpen(t), []);                                          // two top rows: all closed
  assert.deepEqual(defaultOpen(tree([node("x"), node("x-a", { parent: "x" })])), ["x"]);   // one department: open
  const rows = treeRows(t, new Set(["boss"]), { "boss-team-a": 1 });
  assert.deepEqual(rows.map((r) => r.id), ["boss", "boss-team", "boss-sol-1", "loner", MACHINE]);  // sub-departments first
  const team = rows.find((r) => r.id === "boss-team")!;
  assert.equal(team.name, "·team");
  assert.equal(team.open, false);
  assert.deepEqual(team.badges, { ask: 2, red: 0, reply: 1 });                                    // closed = summed below
  assert.equal(team.light, "blue");                                                                // closed = worst below
  const closed = treeRows(t, new Set());
  assert.deepEqual(closed.map((r) => r.id), ["boss", "loner", MACHINE]);
  assert.deepEqual(closed[0].badges, { ask: 2, red: 1, reply: 0 });
  assert.equal(shortName("loner", null), "loner");
  assert.deepEqual(openFor(t, "boss-team-a"), ["boss", "boss-team"]);
  assert.deepEqual(openFor(t, "litellm"), [MACHINE]);
  const all = treeRows(t, new Set(["boss", "boss-team", MACHINE]));
  assert.deepEqual(all.map((r) => [r.id, r.depth]), [["boss", 0], ["boss-team", 1], ["boss-team-a", 2], ["boss-sol-1", 1], ["loner", 0], [MACHINE, 0], ["litellm", 1]]);
});

test("waiting rows (02f §1.3): one of each first, then by order", async () => {
  const { pickWaiting } = await import("./inbox.ts");
  const td = (key: string, kind: "ask" | "red" | "reply" | "wait") => ({ key, kind, title: key, sub: "", at: null, node: null, canDismiss: false });
  const rows = pickWaiting([td("a1", "ask"), td("a2", "ask"), td("a3", "ask"), td("r1", "red"), td("p1", "reply"), td("w1", "wait"), td("bw:x:pick", "wait")], 4);
  assert.deepEqual(rows.map((r) => r.key), ["a1", "r1", "bw:x:pick", "a2"]);
  assert.equal(rows[2].group, "you");
  assert.equal(pickWaiting([], 3).length, 0);
});
