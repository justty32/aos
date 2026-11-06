# Asking the brain

How a brain request travels, what an endpoint pack is, and how priority works.

Your body asks the llm kernel; do not call your brain as a tool. Use this node to choose a child's brain or explain its settings.

The letter: `{"endpoint": "<pack name>", "request": {"messages": [...], "tools": [...]}, "priority": {...}}`, sent with the command `aos-llm ask` (wait for the answer) or `aos-llm send` + `aos-llm recv` (come back later) into `$AOS_LLM_KERNEL/requests/`.

agent-fsm: missing `think/request.json` without pending makes wait exit 11 to think and rebuild. With pending, receive the original reply. Images omit request but keep history, `think/pending.txt` and `think/reply/`.

Endpoint packs: the llm kernel owns a table of named packs, for example `smart-high` (strong, slower, costly), `stupid-fast` (weak, fast, cheap), `fake` (no real model, for tests). A pack fixes the model and sampling settings such as temperature. You pick a pack by name only.

- Do not write `model` or `temperature` in a request. If the pack fixes them, the kernel answers `RequestBad ... is fixed by endpoint <pack>`. To change them, pick another pack.
- Which packs exist: the command `aos-llm ls` prints them with speed and cost.

Priority: optional. `"priority": {"level": "high"}` or `{"level": "high", "deadline": "2026-11-05T10:00:00Z"}`. Higher level and nearer deadline are served first; faster packs go before slower ones at equal level. A letter that waits long is promoted automatically, so nothing starves.

Budgets: daily, per pack and per sender. `BudgetMissing ... max_calls N reached in this window` means the budget is used up for today. The kernel does not switch packs for you; pick a cheaper pack or stop.

Common codes: `EndpointUnknown` (no pack with that name; check `aos-llm ls`), `EndpointFailed` (the model service failed or timed out; try again later), `DeadlineBad` (your deadline passed before it ran), `LlmKernelMissing` (`AOS_LLM_KERNEL` not set; a human must start the llm kernel).
