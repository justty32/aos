// Slash commands combine page actions with the backend-owned CLI command list.
import type { Node, OrderKind, SlashCmd } from "../api/types.ts";
import { COMMAND_WORDS } from "./words.ts";
export interface Command { name: string; label: string; aliases: string[]; group: "talk" | "cli" | "page"; args: SlashCmd["args"]; confirm: boolean; how?: SlashCmd["how"]; cli?: string[] }
export interface CommandCtx { orders: OrderKind[]; slash: SlashCmd[]; cli: string | null; multi: number; target?: string | null }
export const GROUP_WORD = { talk: "對它說／寄", cli: "送進它的畫面", page: "這一頁" };
const PAGE = ["wall", "map", "todo", "up", "decide", "find", "help", "cmds"];
export function parseLine(text: string): { name: string; rest: string } | null {
  if (!text.startsWith("/")) return null;
  const m = /^\/([^\s]*)(?:[ \t]+([^\n]*))?/.exec(text);
  return m ? { name: m[1].toLowerCase(), rest: text.slice(1 + m[1].length).trim() } : null;
}
export function listCommands(ctx: CommandCtx): Command[] {
  const make = (name: string, group: Command["group"], args: Command["args"] = "none"): Command => ({ name, label: COMMAND_WORDS[name]?.label ?? name, aliases: COMMAND_WORDS[name]?.aliases ?? [], group, args, confirm: false });
  const own = [make("say", "talk", "optional"), make("mail", "talk"), ...PAGE.map((n) => make(n, "page", n === "find" ? "optional" : "none"))];
  const cli = ctx.cli ? ctx.slash.filter((s) => s.cli.includes(ctx.cli!) && !own.some((c) => c.name === s.name)).map((s) => ({ ...make(s.name, "cli", s.args), ...s })) : [];
  return [...own.slice(0, 2), ...cli, ...own.slice(2)];
}
export function complete(prefix: string, cmds: Command[]): Command[] {
  const p = prefix.replace(/^\//, "").toLowerCase();
  return cmds.filter((c) => [c.name, ...c.aliases].some((s) => s.startsWith(p)));
}
export function resolve(line: string, ctx: CommandCtx): { cmd: Command; rest: string } | { error: string } {
  const parsed = parseLine(line);
  if (!parsed) return { error: "不是指令" };
  const all = listCommands({ ...ctx, cli: ctx.cli ?? "claude" });
  for (const spec of ctx.slash) if (!all.some((c) => c.name === spec.name)) all.push({ ...spec, group: "cli", label: COMMAND_WORDS[spec.name]?.label ?? spec.name, aliases: COMMAND_WORDS[spec.name]?.aliases ?? [] });
  const cmd = all.find((c) => c.name === parsed.name || c.aliases.includes(parsed.name));
  if (!cmd) return { error: `/${parsed.name} 目前送不進去。${ctx.target || "它"} 的畫面現在只收：${ctx.slash.map((c) => "/" + c.name).join("、")}` };
  if (cmd.group !== "page" && !ctx.target) return { error: "先選一個 agent" };
  if (cmd.group === "cli" && (!ctx.cli || !cmd.cli?.includes(ctx.cli))) return { error: `${ctx.target} 不是 claude／codex 的畫面，收不了這個指令` };
  if (ctx.multi >= 2 && cmd.confirm) return { error: "這個指令一次只能對一個人下" };
  if (cmd.args === "none" && parsed.rest) return { error: `/${cmd.name} 後面不能有字` };
  if (cmd.args === "required" && !parsed.rest) return { error: `/${cmd.name} 後面要有內容` };
  return { cmd, rest: parsed.rest };
}
export function cliProblem(n: Node | undefined, cmd: SlashCmd | undefined): string | null {
  if (!n || n.kind !== "agent") return "先選一個 agent";
  if (!cmd) return "這個指令目前送不進去";
  if (!n.live?.cli || !cmd.cli.includes(n.live.cli)) return `${n.id} 不是 claude／codex 的畫面，收不了這個指令`;
  if (n.state !== "running") return `${n.id} 沒在跑`;
  if (n.queued && cmd.name === "compact") return `${n.id} 信箱還排著 ${n.queued} 封，指令會跟它們併成一批而失效；等它讀完再送`;
  return null;
}
