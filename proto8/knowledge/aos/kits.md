# Kits: ready-made system text and tools for one agent role

A kit is a system text plus a tool set for one role (gatherer, reviewer), laid over a new agent-fsm definition. Kits live in the templates folder, in `templates/kits/` next to `agent-fsm/`; `kits.json` there lists them. A kit is not a template of its own: it is a folder with a system.txt and a tools.json. You make an agent-fsm definition and copy the kit's files over it (a person can instead give the folder to `aos-agent ctl add --kit`).

- How to make an agent from a kit: `aos/kits.md#/Make an agent from a kit`.
- How a kit's system text is built from layers: `aos/kits.md#/Layers of a kit's system text`.
- Why a kit cuts tools, and what it leaves out: `aos/kits.md#/Why a kit cuts tools`.
- What a kit does not enforce yet: `aos/kits.md#/What a kit does not enforce yet`.

# Make an agent from a kit

1. agent_def {"op": "new", "template": "agent-fsm", "path": "defs/gather"}
2. Copy `templates/kits/gather/system.txt` and `templates/kits/gather/tools.json` over `defs/gather/system.txt` and `defs/gather/tools.json` (tools.json names its packs with {"$env": "AOS_HOME"}, so it works wherever it is copied).
3. Set the brain in `defs/gather/llm.json` (aos/brain.md).
4. agent_def {"op": "check", "path": "defs/gather"}: an empty problems list = ready.
5. Start it with subagent add, and give it a brief: the one task, the paths it may read and write, what to deliver in out/, the finish condition (it copies that into its goal), and the knowledge folder path.

For a reviewer, do the same with `templates/kits/review/` (its tools.json is the same as gather's). Several agents of one role can share one definition.

A person attaching an agent from a shell does not copy: `aos-agent ctl add --kit KIT-FOLDER ...` (or `ctl set-def --kit KIT-FOLDER NAME DEF`) writes the kit's system.txt and tools.json into that agent's stack as its own copies, and leaves the definition as it is. Own copies already in the stack are replaced, so giving another kit swaps kits. An eca definition takes a kit too: its system text is appended to the CLI's own and its tools.json replaces the aos tools, but the CLI's built-in tools (Bash, Read...) stay, so the kit's tool limits do not hold on an eca. `aos-agent system reset` and `aos-agent tools reset` drop the kit again.

# Layers of a kit's system text

A system text has no include and no variables: it is sent whole on every brain call, so it is assembled once, when the definition is made, top to bottom:

1. general: `kits/general.A.txt` (tier A = strong general models): start (self_state, read the knowledge base, goal set), workspace folder (notes.md, out/, trash/), work, report (one mailbox_send to the lead), stuck, notice board, stop.
2. site (optional, not shipped): your own rules (who to report to, language, local don'ts, where the notice board is). Put it between general and role.
3. role: `kits/roles/gather.txt` or `kits/roles/review.txt`.
4. task: the brief, sent in the letter that starts the agent; not in system.txt.

general.A.txt has placeholders: `<KNOWLEDGE>` (path of the knowledge folder), `<BOARD>` (how to read a notice board: a command, or a file to read; drop the line if there is none), `<OWN_BOARD>` (how the agent posts who it waits for, or drop the line). The shipped `gather/system.txt` and `review/system.txt` say the brief names the knowledge folder, resolve BOARD to board_read (who = the one waited on, or "user" for the user's notice) and OWN_BOARD to board_wait (who and what when it stops to wait, done = true when the answer comes), and stay within 3,500 characters. If you change a layer, assemble again in the same order.

# Why a kit cuts tools

Every tool's definition is sent on every brain call, so the tool list is the biggest fixed cost, larger than the system text. Characters per pack: `aos/packs.md#/Tool packs`.

The gather tool set keeps look, change (only write, edit, mkdir), gadgets (without do_task), todo, mailbox, comm (only board_read and board_wait; board_set, board_clear and board_ls are turned off), goal, json (read only), index and self_state. It leaves out shell, delete, events, subagent, def, jsonx and kernel_gate. self_tools, self_system, self_llm, self_history and self_ctl are turned off, so the agent cannot give itself back a tool or rewrite its own rules. How a single tool is turned off: aos/packs.md.

# What a kit does not enforce yet

- Writing only in the workspace is a rule in the system text; file tools themselves do not stop a path outside it, and no hook enforces it yet.
- Only a tier A general text and two roles (gatherer, reviewer) exist. A small model may skip parts of the start and stop rules (notes.md, the handoff).
