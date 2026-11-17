// Command tests cover parsing, aliases, backend-only availability, safety rules, history, and pins.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseLine, listCommands, complete, resolve, cliProblem, type CommandCtx } from "./commands.ts";
import { MemoryKv } from "./drafts.ts";
import { recordCommand, readHistory, readPins, togglePin } from "./cmdHistory.ts";
import type { Node } from "../api/types.ts";
const ctx: CommandCtx = { orders: [], slash: [{ name: "compact", args: "optional", confirm: false, how: "turn", cli: ["claude"] }, { name: "clear", args: "none", confirm: true, how: "turn", cli: ["claude"] }], cli: "claude", multi: 0, target: "a" };
test("parse commands only at the first character and complete canonical names or aliases", () => {
  assert.equal(parseLine(" /map"), null); assert.equal(parseLine("hello"), null);
  assert.deepEqual(parseLine("/compact keep\nplan"), { name: "compact", rest: "keep\nplan" });
  assert.deepEqual(complete("/壓", listCommands(ctx)).map((c) => c.name), ["compact"]);
  assert.equal(listCommands({ ...ctx, cli: null }).some((c) => c.group === "cli"), false);
  assert.equal(listCommands(ctx).some((c) => ["hire", "expand", "power"].includes(c.name)), false);
});
test("resolve rejects unknown, non-CLI, multi irreversible commands and invalid arguments", () => {
  for (const [line, c] of [["/unknown", ctx], ["/compact", { ...ctx, cli: null }], ["/clear", { ...ctx, multi: 2 }], ["/mail extra", ctx], ["/mail", { ...ctx, target: null }]] as [string, CommandCtx][]) assert.ok("error" in resolve(line, c));
  assert.equal("cmd" in resolve("/地圖", { ...ctx, target: null }), true);
  assert.equal("cmd" in resolve("/說 /literal", ctx), true);
});
test("CLI preflight rejects stopped and unsupported targets, and blocks queued compact but not usage", () => {
  const n = { id: "a", kind: "agent", state: "running", queued: 0, live: { cli: "claude" } } as Node;
  assert.equal(cliProblem(n, ctx.slash[0]), null);
  const compact = ctx.slash.find((cmd) => cmd.name === "compact")!;
  const usage = { ...compact, name: "usage", args: "none" as const };
  assert.ok(cliProblem({ ...n, queued: 2 }, compact)?.includes("還排著"));
  assert.equal(cliProblem({ ...n, queued: 2 }, usage), null);
  assert.ok(cliProblem({ ...n, state: "stopped" }, ctx.slash[0])); assert.ok(cliProblem(n, undefined));
});
test("command history deduplicates, caps at fifty, and ignores normal text", () => {
  const kv = new MemoryKv(); recordCommand(kv, "hello", null, 0); assert.deepEqual(readHistory(kv), []);
  for (let i = 0; i < 60; i++) recordCommand(kv, "/map " + i, "a", i);
  assert.equal(readHistory(kv).length, 50); recordCommand(kv, "/map 20", "b", 61);
  assert.equal(readHistory(kv)[0].target, "b"); assert.equal(readHistory(kv).filter((x) => x.line === "/map 20").length, 1);
});
test("pins default, toggle, cap at twelve, and tolerate malformed storage", () => {
  const kv = new MemoryKv(); assert.equal(readPins(kv).length, 4); togglePin(kv, "/map"); assert.equal(readPins(kv).includes("/map"), false);
  for (let i = 0; i < 20; i++) togglePin(kv, "/" + i); assert.equal(readPins(kv).length, 12);
  kv.setItem("page.cmd.history", "bad"); assert.deepEqual(readHistory(kv), []);
});

test("backend command lists stay dynamic and page names win collisions", () => {
  const custom = { ...ctx, slash: [...ctx.slash, { name: "screen-tool", args: "required" as const, confirm: false, how: "screen" as const, cli: ["codex"] }, { name: "map", args: "required" as const, confirm: true, how: "turn" as const, cli: ["claude"] }] };
  assert.ok("error" in resolve("/screen-tool", { ...custom, cli: "codex" }));
  const yes = resolve("/screen-tool show", { ...custom, cli: "codex" });
  assert.equal("cmd" in yes && yes.cmd.how, "screen");
  const map = resolve("/map", custom); assert.equal("cmd" in map && map.cmd.group, "page");
  assert.ok("error" in resolve("/compact", { ...ctx, cli: "codex" }));
  assert.ok("error" in resolve("/hire", ctx));
});
