# kernel_llm: one round of the llm kernel

One run = one round, then it exits: the tool folder `$AOS_HOME/lib/tools/aos/kernel_llm`, run by `aos-exec` (`aos-exec $AOS_HOME/lib/tools/aos/kernel_llm [--enable-counters] kernel.json`); you do not run it by hand. A loop runs it again and again: `{"exec": {"argv": ["aos-exec", <kernel_llm>, <kernel.json>]}, "interval_ms": 300}`, so at least 300 ms from the end of one round to the start of the next. That loop is either the own `exec` body of a daemon (the template `templates/kernel/llm-kernel`, its daemon.json) or a looping proc on a daemon you already have (a loop.json with the same two keys; for example a tree's `kernels/llm-gpt` runs as a proc on the ws daemon). Each round is a new process and reads kernel.json again, so an edit to kernel.json counts from the next round, without a restart. Its own errors start with `kernel_llm:`. Start the kernel as its own project:

```sh
cp -r $AOS_HOME/templates/kernel/llm-kernel llms/def
cd llms && aos-exec --stack stacks/llm def      # then point agents at it: AOS_LLM_KERNEL=/abs/llms/stacks/llm
aos-daemon-ctl -d stacks/llm shutdown           # stop it
```

Each round it replies to finished brain calls and picks the best waiting letters from `$AOS_STACK/requests/` for the endpoint packs in `kernel.json` (slots, priority, budget). A bad letter gets an error reply; that is not the kernel's error. Run by hand without `AOS_STACK` = `StackMissing`. Agents only wait (they do not fail) while the kernel is down.

Slots: `slots` (top level of `kernel.json`) is how many brain calls run at once. `reserved` `{"high": N}` keeps N of them for letters with `"priority": {"level": "high"}`: a letter without that level only gets `slots` minus N. The stock agent templates send no priority, so `"slots": 2` with `{"high": 1}` normally runs one call at a time. `reserved.high` must be smaller than `slots`; a wrong value makes every round fail with `CfgBad`, and all letters wait in `requests/new/` until the file is fixed (no restart needed). Waiting letters are in `$AOS_STACK/requests/new/`; letters being answered are in `$AOS_STACK/requests/cur/`.

Timeouts of a pack that calls `llm_http` (the template packs): `connect_timeout_s` (connecting, TLS and sending; default 10) and `read_timeout_s` (the longest wait with no reply data; default 900), in seconds, written in the pack next to `url` and `model`; 0 = no limit. A timeout is `EndpointFailed` with `retry` true.

Where the brain calls run: each one is an add letter to `$AOS_KERNEL` when it is set, else to the ctl mailbox of `$AOS_DAEMON` (the kernel has no `next`). So `unset AOS_KERNEL` in the shell that starts the llm daemon unless you mean it. Hooks (`before_verdict`, `after_verdict`, `before_reply`) go in `kernel_hookeds.json` next to `kernel.json` (named by `"hookeds"` in its `interfaces.json`), written as for a kernel station (aos/kernel.md): exit 10 blocks, a failing hook stops the round with `HookFailed`; `kernel.json` has no `hooks`. The template's `interfaces.json` also names the point declarations (`"hooks": "kernel_hooks.json"`, only for reading) and has `"kernel": {}`. The daemon.json of the template uses `$AOS_HOME`, so `AOS_HOME` must be set when you start it.
