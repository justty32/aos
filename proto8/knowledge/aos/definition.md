# What is in a definition folder

A definition is a folder that says what an agent is (its source code). Its `interfaces.json` names where the other files are, so another definition may name them differently. Below are the names in the two stock templates, `agent-fsm` and `eca-claude` (copy one with `agent_def`).

- Files both templates have: `aos/definition.md#/Files in both templates`.
- Files only one of them has: `aos/definition.md#/Files only one template has`.
- Which files you have your own copy of in your stack: `aos/definition.md#/Your own copy (overlay)`.
- How the two kinds of body differ: `aos/body.md`.

# Files in both templates

- `interfaces.json`: where the other files are (keys `tools`, `llm`, `llm_keys`, `history`, `system`, and `entry` or `screen` under `aos-agent`; `hookeds` and `hooks` at the top level). aos-agent reads only this to find them.
- `_entry`: what runs when the folder itself is run.
- `loop.json`: the loop: what runs each beat, the pause between beats (`interval_ms`), and `on_start` / `on_stop` (they fire the `after_start` / `after_stop` hooks).
- `tools.json`: the tools: the packs listed in `"$override"` plus a few cells (`aos/packs.md`).
- `llm.json`: brain settings, like `{"model": "sonnet"}`; `llm_keys` in interfaces.json says which keys count.
- `system.txt`: the system text. In eca-claude and eca-pi it is two short paragraphs (what aos is, where the knowledge base is), added after the CLI's own system prompt.
- `hookeds.json`: what is hooked (the list `"hookeds"` at the top of `interfaces.json` names; `"hooks"` there names the hook point declarations, only for reading). Both have `timer` (on_clock every 5 minutes, does nothing), `mail_notify` (on_clock every minute: one message when new letters came; `aos/mailbox.md#/Hearing about new letters`), `brain_notify` (brain_failed: BLOCKED letters to `AOS_NOTIFY_BOX`) and `context_wrap` (on_clock: /compact when the context is full enough; `aos/me/compact.md`); eca also has `screen_linger_start` / `screen_linger_stop` (`aos/cli/eca.md#/Delayed screen closure`).
- `_metainfo.json` (summary, cost) and `README.md`: for people and checks.
- `.env` (optional; not in the templates): read from the definition folder when the agent starts. It does not override names already set (PATH, AOS_*) unless added with `aos-agent ctl add --dotenv-override`; for example, `PATH=${HOME}/repo/aos/wf/tools:${PATH}`.

# Files only one template has

Only agent-fsm:

- `body.json`: the body, `aos-loop loop.json`.
- `fsm.json`: the four cells `idle` (take letters from the queue), `think` (ask the brain), `wait` (wait for its answer), `act` (run the tool calls).
- `idle.py`, `brain.py`, `wait.py`, `act.py`, `llm_settings.py`: the programs of those cells; `atomic_file.py`: the atomic file write that idle and wait share; `cell_common.py`: the first steps brain and act share (reading the history, choosing the tool registry); `compact.py`: how a `/compact` letter is done, with the rules of the `before_compact` / `after_compact` hooks, and how a `/clear` letter empties history (`aos/me/compact.md`).
- `subagents.json`: `max_subagents`, how many subagents you may have at once (tool `subagent`).
- A definition may carry none of these programs: when its `fsm.json` names them as `{"$env": "AOS_HOME", "$path": "/templates/agent-fsm/idle.py"}` (the `ann` of the start-api starter does, and so does `fsm=std.fsm()` in an agent.py), the cells run the agent-fsm template's copies under `$AOS_HOME`, and the `hooks` of its `interfaces.json` points at the agent-fsm template's `hooks.json` declaration instead of carrying its own.

Only eca-claude (and eca-pi, the same minus the last two):

- `cli.json`: which outside CLI runs your turns (`kind` claude, codex or pi), its flags, and `timeout_ms` (0 = no limit). aos adds some flags itself; writing one of them in `flags` or `print_flags` is `CfgBad` (codex: `--skip-git-repo-check`, `--json`, `-o`, `--output-last-message`; claude: `-p`, `--print`, `--output-format`, `--session-id`, `--resume`, `-r`, `--continue`, `-c`, `--settings`; pi: `aos/cli/eca.md#/The pi body (kind pi)`).
- `screen/`: the terminal screen a person opens with `aos-agent open`.
- `compact_hook`: Claude Code's own hook around its compaction, firing aos's `before_compact` / `after_compact`.
- `tools_sub.json`: the aos tools of the helpers the claude CLI starts with its Agent tool (read-only: peek_clock, peek_now_time, math, the read-only json tools, index_view).

# Your own copy (overlay)

Some files have a copy with the same name in your stack. When it is there, it is used on top of the definition's. The definition never changes.

| file | your copy holds | change it with |
|---|---|---|
| `tools.json` | only the differences (a removed tool = null) | `self_tools` |
| `llm.json` | only the keys you changed | `self_llm` |
| `system.txt` | the whole text; it replaces the definition's | `self_system` |
| `hookeds.json` | hooks by name (null = turned off) | `self_hook` |
| `subagents.json` | only the keys changed | a human |

`reset` deletes your copy, so the definition's counts again. `history.jsonl` lives only in your stack. The other files (`interfaces.json`, `loop.json`, `fsm.json`, `cli.json` ...) have no copy: to change those, make a new definition with `agent_def`.
