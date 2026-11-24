# aos-llm: ask the llm kernel

send, ask and regret need `AOS_LLM_KERNEL` = the llm kernel's stack (unset = `LlmKernelMissing`). ls selects `--kernel NAME|PATH` first, then `AOS_LLM_KERNEL`, then the only llm kernel row on `$AOS_DAEMON`'s table. A flag value containing `/` is a stack path (relative to the current directory); otherwise it names a table row. No matches or several matches = `LlmKernelMissing` with a `--kernel` hint; several matches list their names. Agents ask through their brain; use this to try endpoint packs by hand.

```sh
aos-llm ls --kernel llm-local     # a named row on AOS_DAEMON's table
aos-llm ls --kernel ./stacks/brain # an explicit kernel stack
aos-llm ls      # fake<TAB>fast<TAB>free<TAB>-<TAB>-<TAB>-<TAB>fake brain: ...
echo '{"request": {"messages": [{"role": "user", "content": "hi"}]}}' | aos-llm ask
# {"role": "assistant", "content": "FAKE ANSWER to: hi"}
echo '{"request": {"messages": [{"role": "user", "content": "two"}]}, "endpoint": "fake", "priority": "high"}' | aos-llm send --reply-to BOX
aos-llm recv BOX LETTER          # exit 10 = no reply yet; --full adds usage, model and letter
aos-llm regret LETTER            # withdraw a request still waiting
```

Automatic detection uses only the row's stack: it must contain both an `endpoints.json` file and a `requests/` directory. Table parts and stack paths relative to the daemon stack are supported.

ls columns (TAB): name, speed, cost, context, slots, backend, summary; the last line is the whole kernel, `# kernel: slots N, reserved for high R, in flight F, queued Q` (`aos/cli/parts/llm_kernel.md`). `--json` prints only the packs. A body without `endpoint` uses the kernel's default pack; an unknown one = `EndpointUnknown`. `send` and `ask` take `--priority P` (overrides the body); `ask --full` prints the same as `recv --full`. The body may also carry `reasoning_effort` (aos/brain.md). `recv --quiet` skips the warning about why there is no reply yet (for polling). `ls --json` prints the window as JSON; `EndpointsMissing`: the kernel has not run yet. `regret` of a letter the kernel already took = `RegretFailed`. Packs and priority: `aos/brain.md`.

More flags: run `aos-llm --help`.
