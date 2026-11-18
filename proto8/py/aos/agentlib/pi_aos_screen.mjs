// pi_aos_screen.mjs - aos's extension for pi's interactive screen: reports turns to aos's hook and hands aos's letters to pi (11-18 eca-pi plan C)
// Loaded through the one-line pi-aos-screen.mjs that cli_pi.py writes into the cell when it opens the screen:
//   import run from "<this file>"; export default function (pi) { run(pi, {python, hook, cell, inbox}); }
// Every report runs `python cli_session.py hook pi CELL` with one JSON object on stdin (cli_hook.pi_hook reads it):
//   session_start {reason, session_id}  agent_start {session_id}  agent_settled {session_id, aborted, messages}
//   compact {session_id, summary}  ack {ids}
// messages are the run's messages from agent_end, cut down to {role, stopReason, text}. A failing hook never stops pi.
// Letters: aos writes <inbox>/*.json ({id, text}); every 0.5 s they are read, deleted, joined with a blank line and sent with
// pi.sendUserMessage (while a turn runs: deliverAs "steer", so the model reads them before its next call), then acked.
import { spawnSync } from "node:child_process";
import { readdirSync, readFileSync, unlinkSync } from "node:fs";

function slim(messages) {
  const out = [];
  for (const m of Array.isArray(messages) ? messages : []) {
    if (!m || (m.role !== "user" && m.role !== "assistant")) continue;
    const parts = Array.isArray(m.content) ? m.content : [];
    const text = typeof m.content === "string" ? m.content
      : parts.filter((p) => p && p.type === "text" && typeof p.text === "string").map((p) => p.text).join("");
    out.push({ role: m.role, stopReason: m.stopReason || null, text });
  }
  return out;
}

export default function run(pi, cfg) {
  let ctx0 = null;
  let run_messages = [];
  const hook = (payload) => {
    try {
      spawnSync(cfg.python, [cfg.hook, "hook", "pi", cfg.cell], { input: JSON.stringify(payload), stdio: ["pipe", "ignore", "ignore"], timeout: 20000 });
    } catch (e) { /* aos's bookkeeping must not break pi */ }
  };
  const sid = (ctx) => {
    try { return ctx.sessionManager.getSessionId(); } catch (e) { return null; }
  };
  pi.on("session_start", async (event, ctx) => {
    ctx0 = ctx;
    hook({ event: "session_start", reason: event && event.reason, session_id: sid(ctx) });
  });
  pi.on("agent_start", async (_event, ctx) => {
    ctx0 = ctx;
    run_messages = [];
    hook({ event: "agent_start", session_id: sid(ctx) });
  });
  pi.on("agent_end", async (event) => {
    run_messages = run_messages.concat(slim(event && event.messages));
  });
  pi.on("agent_settled", async (event, ctx) => {
    const messages = run_messages;
    run_messages = [];
    hook({ event: "agent_settled", session_id: sid(ctx), aborted: !!(event && event.aborted), messages });
  });
  pi.on("session_compact", async (event, ctx) => {
    const entry = (event && event.compactionEntry) || {};
    hook({ event: "compact", session_id: sid(ctx), summary: typeof entry.summary === "string" ? entry.summary : null });
  });

  const poll = () => {
    let names = [];
    try { names = readdirSync(cfg.inbox).filter((n) => n.endsWith(".json")).sort(); } catch (e) { return; }
    if (!names.length || !ctx0) return;
    const ids = [], texts = [];
    for (const n of names) {
      try {
        const doc = JSON.parse(readFileSync(cfg.inbox + "/" + n, "utf8"));
        unlinkSync(cfg.inbox + "/" + n);
        if (doc && typeof doc.text === "string") { ids.push(doc.id); texts.push(doc.text); }
      } catch (e) { /* half-written or already taken: next poll */ }
    }
    if (!texts.length) return;
    const text = texts.join("\n\n");
    let idle = true;
    try { idle = ctx0.isIdle(); } catch (e) { idle = true; }
    try {
      if (idle) pi.sendUserMessage(text); else pi.sendUserMessage(text, { deliverAs: "steer" });
    } catch (e) {
      try { pi.sendUserMessage(text, { deliverAs: "steer" }); } catch (e2) { return; }
    }
    hook({ event: "ack", ids });
  };
  const timer = setInterval(poll, 500);
  if (timer.unref) timer.unref();
  pi.on("session_shutdown", async () => clearInterval(timer));
}
