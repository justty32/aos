# Asking the brain

How a brain request travels, what an endpoint pack is, and how priority works.

Your body asks the llm kernel; do not call your brain as a tool. Use this page to choose a subagent's brain or explain its settings.

The letter: `{"endpoint": "<pack name>", "reasoning_effort"?: "<effort name>", "request": {"messages": [...], "tools": [...]}, "priority": {...}}`, sent with the command `aos-llm ask` (wait for the answer) or `aos-llm send` + `aos-llm recv` (come back later) into `$AOS_LLM_KERNEL/requests/`.

Endpoint packs: the llm kernel owns a table of named packs, for example `smart-high` (strong, slower, costly), `stupid-fast` (weak, fast, cheap), `fake` (no real model, for tests). A pack fixes the model and sampling settings such as temperature. You pick a pack by name only.

- In the letter the pack goes in `endpoint`. Do not put `model` or `temperature` inside `request`: if the pack fixes them, the kernel answers `RequestBad ... is fixed by endpoint <pack>`. To change them, pick another pack.
- This is not the `model` in your brain settings (`llm.json`, changed with `self_llm`, see `aos/me/self_llm.md`). There `model` is the pack name, and your body puts it into `endpoint` for you.
- Which packs exist: the command `aos-llm ls` prints them with speed and cost; `aos-llm ls --json` also shows the `reasoning_efforts` each one accepts.
- Reasoning effort (how hard the model thinks): `"reasoning_effort": "high"` in the letter, next to `endpoint`. It is for the llm kernel, not the same as a `reasoning_effort` you put inside `request` (that one goes to the model service as is). A pack that lists `reasoning_efforts` accepts those names; an effort it does not list is `RequestBad`; a pack without the list ignores the key. In your brain settings it is the key `reasoning_effort`. The template packs keep the prompt cache when you change it.

- Tools in `request.tools`: a pack with `"api": "responses"` (the gpt packs of the `start-api` template) converts them to the Responses API's shape, and sends a function tool that does not say `strict` with `"strict": false`. Without it the Responses API treats the tool as strict and makes every parameter required. A tool that says `strict` is sent as written.

Priority and budgets: `aos/brain.md#/Priority and budgets`. Error codes: `aos/brain.md#/Brain error codes`.

# Priority and budgets

Priority: optional. `"priority": {"level": "high"}` or `{"level": "high", "deadline": "2026-11-05T10:00:00Z"}`. Higher level and nearer deadline are served first; faster packs go before slower ones at equal level. A letter that waits long is promoted automatically, so nothing starves. The kernel may keep some slots for `high` letters only (`reserved`, `aos/cli/parts/llm_kernel.md`), so a letter without a level can wait while a slot looks free.

Budgets: per window (`hour`, `day` or `all`, set by the kernel), in total, per pack and per sender. The sender is your stack (`$AOS_STACK`, the same as the sender on your letters), so each agent has its own count even when agents share a workspace. `BudgetMissing ... max_calls N reached in this window` means the budget of this window is used up. The error object also carries `scope` (total, endpoint or sender), `window`, `since`, `resets_at` (when the next window starts, ISO 8601 with offset; null for `all`), `limit` (`max_calls` or `max_tokens`) and `max`. The kernel does not switch packs for you; pick a cheaper pack or stop. An agent-fsm agent that gets `BudgetMissing` does not stop: it stays waiting and sends the same request again when `resets_at` comes (without that field: after a cooldown of 30 s doubling to 30 min; `aos-agent ctl ls --long` shows it in COOLDOWN and LAST ERROR); its `brain_notify` hook sends one BLOCKED letter per run of refusals to `$AOS_NOTIFY_BOX` (`subagent add` sets it to the parent's mailbox). Changing its brain (`llm.json`) clears that cooldown at once. With window `all` the budget never resets: the agent stops with `BudgetMissing` (exit 1) after the BLOCKED letter; raise the budget, then start it again.

Other brain errors: an agent-fsm agent that gets an error with `retry: true` (see `aos/brain.md#/Brain error codes`) does not stop either: same cooldown (or `retry_after_s` if longer, at most 30 min), same request again, with no limit on tries; `brain_notify` sends one BLOCKED letter when the third failure in a row comes. Any other brain error stops it (exit 1, `BrainFailed`), and `brain_notify` sends a BLOCKED letter saying so; after a start it first waits out the cooldown. Changing `llm.json` clears both cooldowns, and so does `aos-agent ctl retry NAME` from a shell (`aos/cli/agent.md#/Stop, sleep, pause`). The cooldown lives in `cooldown.json` in the agent's stack: `code`, `reason`, `failures`, `until`, `retry` (true = it tries again by itself, false = it stopped on this error) and, from an agent-fsm, `error` (the kernel's `code` and `msg`, e.g. `EndpointFailed` `HTTP 400 ...`); `aos-agent ctl ls --long` shows that error in LAST ERROR; `aos-agent listen` does not read these two fields: it quotes the error lines at the end of the agent's `stderr.txt`, program name included (e.g. `aos-llm: error: EndpointFailed HTTP 400 ...`). Retries are brain calls too and count against budgets: a long outage can use up a window `all` budget, which then stops the agent.

# Brain error codes

`EndpointUnknown` (no pack with that name; check `aos-llm ls`), `EndpointFailed` (the model service failed, timed out or refused), `ReplyBad` (the service answered something that is not a usable reply), `DeadlineBad` (your deadline passed before it ran), `LlmKernelMissing` (`AOS_LLM_KERNEL` not set; a human must start the llm kernel).

Error fields: besides `code` and `msg`, an error may carry `retry` (true = the same request may work later: cannot connect, cut off mid-reply, HTTP 408/429/5xx, a broken reply, or the kernel's own launch/timeout troubles; false or missing = it will not: HTTP 401/403/other 4xx, bad url or key, a bad request), `status` (the HTTP status, when there was a reply), `retry_after_s` (seconds the service asked to wait) and `tries` (how many times the endpoint function called the service: 0, 1 or 2; it already calls once more by itself, after 1 s, when the reply was broken or cut off). Only `retry: true` counts as retryable.
