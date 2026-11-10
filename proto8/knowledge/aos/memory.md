# Writing shared knowledge

Save reusable facts in the knowledge base, not transient task progress.

Write when you discover a verified procedure, a repeated failure and its fix, or a stable fact useful to other agents. Do not store secrets, guesses, or conversation logs. Write only to a knowledge base you are allowed to change; the factory aos knowledge base is owned by humans.

Before writing, call `memory` with `{"op":"find","query":"your topic"}`. Read matching nodes. Update an existing node instead of adding a duplicate. Keep each node at most 2 KB; split a larger topic into child nodes. Use a short title, a one-sentence summary, and concrete examples.

If `memory_write` is not registered, ask a human to register the prepared `tools/memory_write` tool. It shares the root configured for `memory`. `self_tools` can add it only if its path is allowed: see node `me/self_tools`.

Call `memory_write` with `{"op":"add","path":"topic","text":"# Topic\n\nOne-sentence summary.\n"}` to add a node. Use `edit` with the complete replacement text to update it. Read the node again before editing; another agent may have changed it.

If a write returns `LockFailed`, wait briefly and retry once. If it fails again, stop and report; do not bypass the lock or retry in a loop.
