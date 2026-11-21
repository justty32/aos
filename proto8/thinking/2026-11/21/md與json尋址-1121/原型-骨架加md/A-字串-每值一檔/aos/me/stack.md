# What is in your stack

Your stack is `$AOS_STACK`, the folder where you keep your state.

- `history.jsonl`: your conversation, one JSON message per line. Your body appends to it. Never edit it by hand; to change it use `self_history`.
- `queue/`: your queue. Humans and other agents drop letters here; you answer them in order.
- `letters.json`: `pending` = letters your body has taken and not answered yet; `dropped` = the last 50 letters it will not answer (`letter`, `reason`: `bad` letter, `blocked` by a hook, or `failed` after it was handed over; `at`). Your body writes it; `aos-agent ask` and `listen` read it, with the `aos` key of history rows (`aos/body.json#/system_history`), to find the answer to one letter. Not by hand.
- `tools.json`: your own tool registry. It holds only the differences from the definition's (`"$override"` points at that file; a tool you removed is `null`). Written by `self_tools`, not by hand.
- `llm.json`: your brain overlay (for example which model you use). Written by `self_llm`.
- `system.txt`: your own system text, when you set one with `self_system`.
- `hookeds.json`: your own hooks, written by `self_hook`; `hookeds/<name>/`: each hook's own folder.
- `subagents.json`: your own quota change (`max_subagents`), when a human set one.
- `mailbox/`: letters to you (`aos/mailbox.json`).
- `tools/<name>/`: a scratch folder for each tool you call (made only when that tool writes something there).

Which definition files have your own copy here, and what each holds: `aos/definition.json#/overlay`.
