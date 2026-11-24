# kits

This folder holds kits: ready-made system texts and tool sets for one agent role, laid over the agent-fsm template.
A kit is not a template of its own: it is a folder with a `system.txt` and a `tools.json`, laid over an agent-fsm definition.

## What a kit is

A kit is the system text plus the tool set (and, later, hooks and brain settings) for one role. Kits shipped here:

| kit | role | system | tools |
|---|---|---|---|
| gather | gatherer: finds facts with sources, does not design | [gather/system.txt](gather/system.txt) | [gather/tools.json](gather/tools.json) |
| review | reviewer: checks work against a brief, points out, does not fix | [review/system.txt](review/system.txt) | [review/tools.json](review/tools.json) (the same file as gather's) |

[kits.json](kits.json) lists the same in machine-readable form.

The `.txt` files have no description line at the top, because the whole text is sent to the model; this README describes them instead.

## Layers

A system text is assembled from layers, top to bottom:

1. **general** - [general.A.txt](general.A.txt), for strong general models (tier A): start, folder, work, report, stop rules.
2. **site** (optional, not shipped) - your own layer: who to report to, local rules, language, where your notice board is.
3. **role** - [roles/gather.txt](roles/gather.txt), [roles/review.txt](roles/review.txt).
4. **task** - the brief, sent in the letter that starts the agent.

Placeholders in general.A.txt:

- `<KNOWLEDGE>` - path of the aos knowledge folder.
- `<BOARD>` - how to read a notice board (a command such as board_read, or a file to read). Leave the whole BOARD line out if your site has none.
- `<OWN_BOARD>` - a line saying how the agent posts who it waits for (board_wait), or remove the line.

The shipped `gather/system.txt` and `review/system.txt` are general.A.txt with these defaults, then a blank line, then the role text: step 2 of START says to read `aos/_description.md` in the knowledge folder the brief names; the BOARD line says to board_read someone before waiting on them and when an answer is late (`"user"` for the user's notice); the `<OWN_BOARD>` line becomes an OWN BOARD line: board_wait with who and what when it stops to wait, board_wait with done = true when the answer comes. Each stays at or below 3,500 characters. If you change a layer, assemble again in the same order (tests/kits/test_kits.py checks this).

## How to use

A person, from a shell: give the kit folder to `aos-agent ctl add` or `ctl set-def` with `--kit`.

```
aos-agent ctl add --kit $AOS_HOME/templates/agents/kits/gather -n gat -w . agents/ann
aos-agent ctl set-def --kit $AOS_HOME/templates/agents/kits/review ann agents/ann
```

The kit's two files are written into the agent's stack as its own copies (the layer that `aos-agent system set` and `aos-agent tools add` write); the definition folder is not changed, so several agents can share one definition with different kits. agent-fsm reads them on every brain call. Own copies already in the stack (an earlier kit, `system set`, `tools add`) are replaced, so to swap kits just give `--kit` again. An eca definition (with `cli.json`) takes a kit too: the system text is appended to the CLI's own and the tools replace the aos tools, but the CLI's built-in tools (Bash, Read...) stay, so the kit's tool limits do not hold there (a `cli.json` that names its own `tools` is refused, `KitBad`). To drop a kit:

```
aos-agent -t ann system reset -y
aos-agent -t ann tools reset -y
```

An agent, with its tools: make a definition and copy the kit's files over it.

```
agent_def {"op":"new","template":"agent-fsm","path":"defs/gather"}
```

Then copy `kits/gather/system.txt` and `kits/gather/tools.json` over the new definition's `system.txt` and `tools.json`, set the brain in its `llm.json` yourself, and run `agent_def check`.

For a reviewer, do the same with `kits/review/`.

A kit of your own is any folder with these two files. `tools.json` must name its packs with `{"$env": "AOS_HOME"}` or absolute paths (as the shipped ones do), not paths relative to the kit, because it is copied into the stack.

## Why tools are cut

Tool descriptions are the biggest fixed cost of every brain call: they are sent each time. Measured 2026-11-14:

| | tools | chars of the tool list sent | of which descriptions |
|---|---:|---:|---:|
| agent-fsm template as shipped | 55 | about 85,700 | about 37,000 |
| gather kit | 24 | about 30,100 | about 13,800 |

Cutting tools saves far more than cutting the system text. board_read and board_wait were added after this measurement (now 26 tools).

The gather tool set (26 tools) keeps reading, write/edit/mkdir, gadgets, todo, mailbox, board_read and board_wait (from the comm pack; board_set, board_clear and board_ls are turned off), goal, read-only json, index and self_state. It leaves out shell, delete, events, subagent, def, jsonx and kernel_gate. self_tools, self_system, self_llm, self_history and self_ctl are turned off, so the agent has no tool for lifting its own limits. It still has write and edit, which take absolute paths, so it can reach the `tools.json` in its own stack; only the rules keep it from editing that file by hand.

## Known limits

- Writing only inside the workspace is a convention in the system text; no hook enforces it yet.
- Turning off the self tools does not lock the tool set: write and edit can still change the `tools.json` in the agent's own stack.
- board_read and board_wait run the `aos-comm` command, so it must be on PATH (`source "$AOS_HOME/env.sh"` puts `$AOS_HOME/bin` there); without it those two calls fail and the rest of the kit still works.
- Only tier A general text and two roles exist so far.
