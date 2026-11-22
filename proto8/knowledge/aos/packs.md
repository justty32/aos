Your tools come in packs. Which packs you have, what each tool does in one sentence, and how a pack is turned off.

# _index

- Tool packs: How packs work, which ones agent-fsm has, what each costs, how to add or turn one off.
- look: Pack look: read, ls, view, stat, grep, glob; look at and search files, change nothing.
- change: Pack change: write, edit, copy, move, mkdir; make and change files.
- delete: Pack delete: trash (can be undone), remove (cannot).
- shell: Pack shell: shell, run_python; run a command, read its output and exit code.
- gadgets: Pack gadgets: peek_clock, peek_now_time, math, do_task (fold one task of your own history into a summary; agent-fsm only).
- events: Pack events: clock_register (clock letters to your queue: every N cycles, once, at a wall-clock time, or cron), self_hook (run a program when something happens to you).
- todo: Pack todo: todo (your own to-do list for a long task: ls, set, add, mark).
- self: Pack self: self_tools, self_llm, self_system, self_history, self_state, self_ctl; look at and change your own copy.
- subagent: Pack subagent: subagent (helpers you start yourself), agents_ctl (any agent on your daemon), fork (a copy of yourself for one goal; agent-fsm only).
- def: Pack def: agent_def (new agent definitions), tools_def (new tools).
- mailbox: Pack mailbox: mailbox_peek, mailbox_read, mailbox_send; letters between agents.
- goal: Pack goal: goal (one sentence you keep working on; reminded when you stop by yourself).
- json: Pack json: json_get, json_ls, json_search, json_len, json_set, json_add, json_del, json_multi_get, json_multi_set; one place of a JSON file at a time by FILE#/POINTER.
- jsonx: Pack jsonx: jsonx_get, jsonx_ls, jsonx_search, jsonx_set, jsonx_add, jsonx_del, jsonx_multi_get, jsonx_multi_set; JSON tools that follow or resolve $ref/$env.
- comm: Pack comm: board_set, board_clear, board_wait, board_read, board_ls; a public board of what you are doing and whom you wait for. Used by the kits, in no stock definition.
- index: Pack index: index_view; see a node through its index, change nothing.
- kernel_gate: Pack kernel_gate: kernel_gate; be a kernel gate (requests come to you, you decide, a station on you forwards). In no stock definition.

# Tool packs

Your tools are registered pack by pack: each pack is one tool list in $AOS_HOME/lib/packs/<pack>.json, and a definition's tools.json stacks the packs it wants with "$override". agent-fsm has eleven packs (look, change, delete, shell, gadgets, todo, self, mailbox, goal, json, index) with four self tools turned off: 36 tools. Of the self pack only self_tools and self_state are on; add self_llm, self_system, self_history or self_ctl yourself when you need one: self_tools {"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_llm"}}. Four more packs are optional, in no stock template (agent-fsm or eca): events, subagent, def and jsonx. The kits (aos/kits.md) also use the comm pack (boards: what you are doing, whom you wait for). eca-claude has five (gadgets, self, mailbox, json, index; no look, change, delete, shell, subagent, goal or todo pack: its CLI has its own file tools, shell, helpers, goals and todo lists; no events, def or jsonx pack since 2026-11-22) and turns off do_task (agent-fsm only) and the same four self tools as agent-fsm (self_llm, self_system, self_history, self_ctl): 18 tools; eca-pi has the same list. On an eca, add a tool of events, def or jsonx yourself when you need it, one at a time: self_tools {"op": "add", "path_json": {"$env": "AOS_HOME", "$path": "/lib/tools/agent/self_hook"}} (clock_register, agent_def and tools_def are in /lib/tools/agent/ too; the jsonx tools in /lib/tools/aos/, like /lib/tools/aos/jsonx_get). The subagents of an eca (tools_sub.json) get no jsonx. One more pack, kernel_gate, is in no stock definition: add its tool yourself with self_tools (`aos/kernel.md#/Being a kernel yourself: kernel_gate`).

One more optional pack, ws-write (tool ws_write), writes text files only inside your own workspace (create, append, replace; 262144 bytes per call; paths inside your own stack or definition, other agents' stacks or any .stack folder are refused). It is in no stock definition; a definition adds lib/packs/ws-write.json to its "$override".

What a pack costs: every pack you have is sent with every question to your brain (each tool's name, description and parameters). Characters per pack, as sent:

| pack | tools | characters |
|---|---|---|
| look | 6 | 4,755 |
| change | 5 | 2,294 |
| delete | 2 | 775 |
| shell | 2 | 1,010 |
| gadgets | 4 | 1,623 |
| todo | 1 | 1,034 |
| self | 6 | 5,407 |
| mailbox | 3 | 2,343 |
| goal | 1 | 867 |
| json | 9 | 4,834 |
| index | 1 | 803 |
| events (optional) | 2 | 10,263 |
| subagent (optional) | 3 | 10,940 |
| def (optional) | 2 | 6,427 |
| jsonx (optional) | 8 | 11,961 |
| comm (optional) | 5 | 6,120 |
| ws-write (optional) | 1 | 1,067 |
| kernel_gate (optional) | 1 | 1,410 |

The eleven agent-fsm packs as shipped (self pack with only self_tools and self_state, about 2,100 of its 5,407): 36 tools, about 22,500 characters. Measured 2026-11-21, after the tool descriptions of the stock packs were cut to a sentence or two with a pointer to their knowledge page; the optional packs keep their longer descriptions.

How to add a pack: whoever makes the definition adds one item to "$override" in its tools.json, for example {"$env": "AOS_HOME", "$path": "/lib/packs/subagent.json"}; a kit can add it too (aos/kits.md). Add it when the definition is made, not while the agent runs: self_tools add takes one tool at a time, and every change to your tool list makes the brain lose the cached start of your conversation.

- See where each of your tools comes from: self_tools {"op": "ls", "long": true} (FROM shows lib/packs/<pack>.json).
- Turn one tool off for yourself: self_tools {"op": "rm", "name": "shell"}.
- A whole pack is turned off by removing it from the "$override" list of the definition's tools.json (a person or a definition change, not a tool call).
- A tool whose description starts with `[MCP server NAME]` comes from an external MCP server, not from a stock pack: `aos/cli/mcp_import.md#/Where an external tool comes from`.

# look

Pack look: Read-only file tools: read (a text file), ls (a folder), view (a file with its type), stat (facts about one path), grep (search inside files, like grep -rn), glob (find files by name pattern). One node per tool: aos/tools/read.md, aos/tools/ls.md, aos/tools/view.md, aos/tools/stat.md, aos/tools/grep.md, aos/tools/glob.md.

# change

Pack change: Editing files: write (whole file), edit (replace exact text), copy, move (also rename), mkdir. One node per tool: aos/tools/write.md, aos/tools/edit.md, aos/tools/copy.md, aos/tools/move.md, aos/tools/mkdir.md.

# delete

Pack delete: trash (move into your workspace .trash/, can be moved back) and remove (delete for real; a folder needs recursive). One node per tool: aos/tools/trash.md, aos/tools/remove.md.

# shell

Pack shell: shell (one bash command; not a sandbox) and run_python (a short Python program). One node per tool: aos/tools/shell.md, aos/tools/run_python.md.

# gadgets

Pack gadgets: Small handy tools: peek_clock (the daemon clock: current cycle and interval_ms; ClockMissing when you have no daemon clock), peek_now_time (current UTC time, or local time with local: true), math (one arithmetic expression), do_task (agent-fsm only: start a task in your own conversation and end it with a summary that replaces its messages; see aos/me/do_task.md).

# events

Pack events: Things that run later: clock_register (a fixed letter every N cycles, once after N cycles, at a wall-clock time, or by cron; leave out box to wake yourself; aos/clock.md) and self_hook (run a program when something happens to you).

# self

Pack self: Look at and change yourself: self_tools (your tools), self_llm (your brain settings), self_system (your system text), self_state (facts and numbers about you), self_ctl (stop, pause, sleep or remove yourself), self_history (your conversation). agent-fsm as shipped has only self_tools and self_state on; add the others with self_tools.

# subagent

Pack subagent: Other agents: subagent (agents you start yourself; counted against your quota) and agents_ctl (any agent on your daemon table; not counted), and fork (agent-fsm only: a copy of yourself, settings and whole conversation, for one goal; only its short conclusion comes back; see aos/agents/fork.md).

# def

Pack def: Definitions: agent_def (copy a template into a new agent definition, or check one) and tools_def (make a new tool from the Python skeleton, or check a tool).

# mailbox

Pack mailbox: Letters: mailbox_peek (what is waiting, without taking it), mailbox_read (read the oldest), mailbox_send (send one).

# goal

Pack goal: goal keeps one sentence you are working on (get, set, done, pause, resume) in your stack. When you stop by yourself (your answer calls no tool) and no letter waits, aos gives you a short "[aos] goal: ..." reminder; done or pause stops the reminders. In agent-fsm, after you pause your own goal and a message comes, you get one "[aos] goal: paused ..." note asking whether to resume, finish or keep waiting; the goal itself is not resumed. One node: aos/tools/goal.md.

# todo

Pack todo: todo keeps your own to-do list for a long task (ls, set, add, mark) in your stack, outside your history; it is not shown to you by itself, so call ls to see it again. One node: aos/tools/todo.md.

# json

Pack json: Plain JSON, one place at a time, the path always `FILE#/POINTER`: json_get (one value), json_ls (what is inside, like ls), json_search (find a key or value), json_len (the length: keys, items or characters), json_set (set a value), json_add (add a key or array item, never overwrite), json_del (delete one); json_multi_get and json_multi_set do several places in one call, one result line each. Values are stored exactly as given; `$ref`/`$env` objects are plain objects. One node per tool: aos/tools/json_get.md, aos/tools/json_ls.md, aos/tools/json_search.md, aos/tools/json_len.md, aos/tools/json_set.md, aos/tools/json_add.md, aos/tools/json_del.md, aos/tools/json_multi_get.md, aos/tools/json_multi_set.md.

# jsonx

Pack jsonx: For aos configuration files that use `$ref`/`$env`: jsonx_get, jsonx_ls and jsonx_search (follow, resolve), jsonx_set and jsonx_add (value, text or from; follow, resolve, check), jsonx_del (follow); jsonx_multi_get and jsonx_multi_set do several places in one call, the options set once for all. No stock template has it (agent-fsm, eca-claude, eca-pi); a definition adds it, or you add one tool at a time with self_tools. One node per tool: aos/tools/jsonx_get.md, aos/tools/jsonx_ls.md, aos/tools/jsonx_search.md, aos/tools/jsonx_set.md, aos/tools/jsonx_add.md, aos/tools/jsonx_del.md, aos/tools/jsonx_multi_get.md, aos/tools/jsonx_multi_set.md.

# comm

Pack comm: boards, a short public note on your stack that says what you are doing and whom you are waiting for, so others (and the user's overview page) can read it before sending you letters: board_set (post your board: mode here, busy, dnd or away, what you are doing, when you are back), board_clear (take it down), board_wait (add or remove a line of who you are waiting for), board_read (read one board: an agent's, the user's or your own) and board_ls (everyone on your daemon table). In no stock definition; the kits add it (aos/kits.md). These tools have no page of their own yet: each tool's description says how to call it.

# index

Pack index: index_view, see a node through its index (the notes agents keep about what is under it); change an index with the json tools. One node: aos/tools/index_view.md.

# kernel_gate

Pack kernel_gate: kernel_gate makes you a kernel gate: other procs send their requests to start or change procs to a mailbox of yours, a kernel station hooked on you holds each one, you are told ("[aos] kernel_hold: ...") and decide with op pass or op refuse, and the station forwards what you pass. Not in any stock definition; add it with self_tools {"op": "add", "path": "<AOS_HOME>/lib/tools/agent/kernel_gate"}. See `aos/kernel.md#/Being a kernel yourself: kernel_gate`.
