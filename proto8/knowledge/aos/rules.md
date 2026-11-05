# Boundaries

What you must not do, and why. Read this before doing anything that changes the system.

Never:

1. Edit a definition folder. It is source code shared by every instance; humans own it. Per-instance changes go in your overlay (`self_tools` for tools; a human's `aos-agent llm set` for the brain).
2. Touch another agent's stack or the daemon's own files. Talk to agents with letters (`agents` say/ask); never write into their folders.
3. Rewrite `history.jsonl`. It is append-only; the body appends for you.
4. Work around a refusal. `AddRejected`, `BudgetMissing`, `PhaseBad` are decisions by the kernel or the daemon. Adapt or report; do not retry the same call, rename things to slip past a whitelist, or start a second daemon.
5. Use shell tricks to do what a tool should do (for example `bash` to copy a tool into your definition, or to send letters by hand). If no tool exists for the job, say so.
6. Leave children running. Remove child agents you started once their work is done.
7. Delete anything outside your workspace. Inside it, delete only what you created or were asked to delete.

Always:

- Keep paths relative to your workspace. A path that resolves outside it is refused (`PathBad`) on purpose.
- After one failure, read the Code before retrying (node `errors`). Two identical failures in a row mean stop and report.
- Report limits as facts: "the daemon allows 4 agents and 4 are running" is a complete, correct answer.
- Prefer the smallest change that works: add one tool, not five; one child, not a tree of them.

Why: aos runs many agents on one machine with shared folders. The rules keep one agent's mistake from reaching the others, and keep what a human reads in the table (`reason`, `tools overlay`) truthful.
