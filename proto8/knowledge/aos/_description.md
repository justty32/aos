# aos in one page

What aos is, the eight words you need, and how to look up more.

aos runs AI agents as ordinary Linux processes inside folders. You are one of those agents. Everything you touch is a folder or a file; every action is a tool call.

The eight words:

- **definition**: a folder that says what an agent is (its source code). Do not edit yours: the `self_*` tools change your own copy in your stack instead.
- **stack**: the folder where one running agent keeps its state (its memory). Yours is `$AOS_STACK`.
- **workspace (ws)**: the folder you work on (your external memory). Yours is `$AOS_WS`. Paths you give to tools are relative to it.
- **daemon**: the machine. It runs agents and keeps a table of them (name, phase, reason). Yours is `$AOS_DAEMON`.
- **proc**: one running thing under a daemon. A running agent is a proc.
- **kernel**: wherever you send a request (start a proc, ask the brain). It decides whether and when the request runs. The daemon itself is the simplest kernel; a kernel station can sit in front of it and refuse. See aos/kernel.md.
- **letter / mailbox**: how procs talk. A letter is a folder with a letter.json, dropped into a mailbox folder. Asking the brain is a letter to the llm kernel.
- **tool**: a folder you can call. You call it with a JSON object; it answers on stdout. On failure it prints one line `toolname: error: Code reason`.

Five rules:

1. Never edit a definition by hand or touch another agent's stack. Change yourself through the `self_*` tools; make new kinds of agents with `agent_def` (see `aos/rules.md`).
2. Use tools, not shell tricks. If no tool fits, say so instead of improvising.
3. When a tool fails, read the error line. The Code tells you what kind of problem it is; fix that, then retry once. Do not retry the same call in a loop.
4. Paths are relative to your workspace unless a tool says otherwise.
5. If something is refused (a kernel said no, a budget is used up), that is a decision, not a bug. Report it or adapt; do not force it.

Which version these files describe: `.aos-source.json` in the knowledge folder (one level up from `aos/`) records the aos repo commit they were copied from and when; the repo may be newer. No such file means a copy of unknown version.

To learn more, read the files next to this one: `_index.json` in this folder says in one sentence what each one is about. A page is a `.md` file (text, one section per heading) or a `.json` file (short data). `json_get` and `json_ls` read both: `aos/me.md#/What is in your stack` is the section under that heading, `json_ls` on `aos/me.md` lists its headings; rules in `aos/tools/json_get.md#/JSON tools: reading markdown`. Start with `aos/me.md` if the question is about yourself, `aos/errors.md` if a tool failed.
