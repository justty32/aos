Demo only (not in knowledge/): proto8/knowledge/aos/body.md rewritten with key points on top and one fact per line, eca and agent-fsm kept apart. Same facts as the live page; the two linked headings keep their names.

# Two kinds of body

Key points:

- Your body is the program that runs your turns: agent-fsm (aos's own loop) or eca (Claude Code, Codex CLI or pi runs your turns).
- Find out which: `self_state` `{"parts": ["who"]}` gives your definition folder; `cli.json` there = eca, `fsm.json` = agent-fsm.
- eca: the CLI's own tools do files and commands; your aos tools come through aos-mcp as `mcp__aos__...`.
- eca: aos hooks see only aos tools; to guard Bash and the other CLI tools, use the CLI's own hooks.
- Every eca turn costs the CLI's money.

More:

- Brain, tools, hooks, screen: `aos/body.md#/Brain, tools, hooks, screen`.
- System text, history: `aos/body.md#/System text, history`.
- The files of each body: `aos/definition.md`.

The two kinds:

- agent-fsm: aos's own loop with four cells (idle, think, wait, act). Your brain is asked with a letter to the llm kernel; aos runs each tool call.
- eca (an outside coding agent): Claude Code, Codex CLI or pi runs your turns. aos hands it your queue letters and your aos tools, and writes its answer to your history.

# Brain, tools, hooks, screen

Brain:

- eca: the CLI is the brain. Only `model` and `reasoning_effort` count: claude `--effort`, pi `--thinking`, codex takes none.
- agent-fsm: each think step is a letter to the llm kernel. `model` names a brain pack; keys like `temperature` tune it.

Tools:

- eca, files and commands: the CLI's own tools. claude template: Read, Write, Edit, Glob, Grep, Bash, Agent, Skill. pi: its own tools. codex: its own shell in a workspace-write sandbox.
- eca, aos tools: through aos-mcp, named like `mcp__aos__peek_now_time`. No aos file or shell tools; the json pack is there (json_get, json_set, ...).
- agent-fsm: only your registered aos tools.
- Both: a tool added with `self_tools` can be called from your next reply.

Hooks:

- eca: `before_tool` / `after_tool` see only aos tools. The CLI's own tools (Bash, Write, Edit ...) and what a person types on the screen are not seen.
- eca: to check or block the CLI's own tools, use the CLI's own hooks: `aos/cli/eca.md#/Guarding the CLI's own tools (claude)`.
- agent-fsm: every event.

When `on_clock` is checked (`aos/me/self_hook.md#/The on_clock hook`):

- eca: every time your loop comes round while you are idle (stock template: about three times a second), new messages or not.
- eca: not while aos waits for the CLI to answer a queue message.
- agent-fsm: at the start of each cell.
- Both: not while you sleep, and never when there is no clock.

Screen (eca only; agent-fsm has none):

- A person opens it with `aos-agent open`.
- claude with its screen open gets each queue letter at once as a signed message (`Message from @NAME`, or `@aos通知中心` for notices), even in the middle of a turn. It is not text typed by its user (`aos/cli/eca.md#/aos-eca-turn: one turn`).
- The screen gets `AOS_CLOCK`, `AOS_KERNEL` and `AOS_LLM_KERNEL` as your loop has them, not from that person's shell.
- A screen opened before your loop ran once may lack them: `ClockMissing` (`aos/clock.md#/Clock letters: rules`). Have it closed and opened again.

# System text, history

System text (`self_system`):

- eca claude: added after Claude Code's own system text, from your next turn.
- eca codex: added only when a new conversation starts, so a change waits for the next new conversation. aos does not start one for you.
- eca pi: added to pi's system prompt, read again every turn.
- agent-fsm: your text is the whole system message, read again before every brain call. Empty = no system message.

History (`history.jsonl` in your stack):

- eca: the CLI keeps its own conversation. `history.jsonl` holds your queue letters and the CLI's final answer of each turn, not its tool calls.
- eca: after `self_history` changes it, the next turn starts a new conversation that carries the changed record.
- agent-fsm: the conversation sent to the brain, tool calls and results included.

Marks on history rows (both bodies):

- A row that came from a letter has `"aos": {"letter": "<letter name>"}`.
- A final answer (assistant, no `tool_calls`) has `"aos": {"answer_to": ["<letter name>", ...]}`, the letters it answers.
- agent-fsm takes the `aos` key off each row before it sends the conversation to the brain: the model never sees it.
- An `aos` key written in a letter is replaced.

Cache: a change to system text or history makes the next brain call miss the prompt cache once.
