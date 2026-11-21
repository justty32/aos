# Changing your own system text

Tool `self_system` is `aos-agent system` aimed at you; only your own copy changes, not your definition.

- see: `{"op": "get"}` (`"long": true` adds a first line FROM TAB FILE: agent, definition or none)
- change: `{"op": "set", "text": "..."}` (the whole new text; `get` first to keep the old lines)
- undo: `{"op": "reset"}`

When it works: agent-fsm = your next brain call (it replaces the definition's; empty = no system message); eca claude = your next turn (appended); eca codex = your next new conversation; eca pi = your next turn (appended); an open screen = when it is reopened.

Each change makes your prompt cache miss once: change it when your job changes, not every turn. A broken text is fixed by a human: `aos-agent system --target <you> reset`. Model settings are `self_llm`. `SystemMissing` = your definition declares no system file. `SystemBad` = your copy or your definition's system file cannot be read, or the definition declares it wrongly; a human must fix it.

Why it differs by body (and what history does): `aos/body.md#/System text, history`.
