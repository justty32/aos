# Asking the brain

How a brain request travels, what an endpoint pack is, and how priority works.

Your own thinking is already wired: your body sends your conversation as a letter to the llm kernel and waits for the reply. You do not call the brain as a tool. This node matters when you choose a brain for a child agent, or when a human asks you about brain settings.

The letter: `{"endpoint": "<pack name>", "request": {"messages": [...], "tools": [...]}, "priority": {...}}`, sent with the command `aos-llm ask` (wait for the answer) or `aos-llm send` + `aos-llm recv` (come back later) into `$AOS_LLM_KERNEL/mailbox/`.

Endpoint packs: the llm kernel owns a table of named packs, for example `smart-high` (strong, slower, costly), `stupid-fast` (weak, fast, cheap), `fake` (no real model, for tests). A pack fixes the model and sampling settings such as temperature. You pick a pack by name only.

- Do not write `model` or `temperature` in a request. If the pack fixes them, the kernel answers `RequestBad ... is fixed by endpoint <pack>`. To change them, pick another pack.
- Which packs exist: the command `aos-llm ls` prints them with speed and cost.

Priority: optional. `"priority": {"level": "high"}` or `{"level": "high", "deadline": "2026-11-05T10:00:00Z"}`. Higher level and nearer deadline are served first; faster packs go before slower ones at equal level. A letter that waits long is promoted automatically, so nothing starves.

Budgets: each pack and each sender can have a budget per day. `BudgetMissing ... max_calls N reached in this window` means the budget is used up for today. The kernel does not switch packs for you; pick a cheaper pack or stop.

Common codes: `EndpointUnknown` (no pack with that name; check `aos-llm ls`), `EndpointFailed` (the model service failed or timed out; try again later), `DeadlineMissed` (your deadline passed before it ran), `LlmKernelMissing` (`AOS_LLM_KERNEL` not set; a human must start the llm kernel).
