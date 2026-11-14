# kits

This folder holds kits: ready-made system texts and tool sets for one agent role, laid over the agent-fsm template.
A kit is not a template of its own; you copy its files over a new agent-fsm definition.

## What a kit is

A kit is the system text plus the tool set (and, later, hooks and brain settings) for one role. Kits shipped here:

| kit | role | system | tools |
|---|---|---|---|
| gather | gatherer: finds facts with sources, does not design | [gather/system.txt](gather/system.txt) | [gather/tools.json](gather/tools.json) |
| review | reviewer: checks work against a brief, points out, does not fix | [review/system.txt](review/system.txt) | [gather/tools.json](gather/tools.json) (same) |

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
- `<BOARD>` - how to read a notice board (a command, or a file to read). Leave the whole BOARD line out if your site has none.
- `<OWN_BOARD>` - empty for now; remove the line.

The shipped `gather/system.txt` and `review/system.txt` are general.A.txt with these defaults, then a blank line, then the role text: step 2 of START says to read `aos/_description.json` in the knowledge folder the brief names; the BOARD line says to check a notice board only if the brief names one; the `<OWN_BOARD>` line is dropped. Each stays at or below 3,000 characters. If you change a layer, assemble again in the same order (tests/kits/test_kits.py checks this).

## How to use

```
agent_def {"op":"new","template":"agent-fsm","path":"defs/gather"}
```

Then copy `kits/gather/system.txt` and `kits/gather/tools.json` over the new definition's `system.txt` and `tools.json`, set the brain in its `llm.json` yourself, and run `agent_def check`.

For a reviewer, do the same but take `system.txt` from `kits/review/`; the tools are the same as gather.

## Why tools are cut

Tool descriptions are the biggest fixed cost of every brain call: they are sent each time. Measured 2026-11-14:

| | tools | chars of the tool list sent | of which descriptions |
|---|---:|---:|---:|
| agent-fsm template as shipped | 55 | about 85,700 | about 37,000 |
| gather kit | 24 | about 30,100 | about 13,800 |

Cutting tools saves far more than cutting the system text.

The gather tool set keeps reading, write/edit/mkdir, gadgets, todo, mailbox, goal, read-only json, index and self_state. It leaves out shell, delete, events, subagent, def, jsonx and kernel_gate. self_tools, self_system, self_llm, self_history and self_ctl are turned off, so the agent cannot lift its own limits.

## Known limits

- Writing only inside the workspace is a convention in the system text; no hook enforces it yet.
- Only tier A general text and two roles exist so far.
