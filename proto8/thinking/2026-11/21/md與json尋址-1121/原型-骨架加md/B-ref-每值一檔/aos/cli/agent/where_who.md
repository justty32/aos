# Finding agents and stacks

```sh
aos-agent ctl where bob          # its stack
aos-agent ctl where --ws bob     # its workspace
aos-agent ctl who                # the owner of $AOS_STACK, also from a nested tool stack
aos-agent ctl who --stack /path/to/stack --json
# {"name": "ann", "stack": "...", "ws": "...", "def": "...", "daemon": "...", "parent": null, "notify_box": null}
```

`parent` and `notify_box` are what the requester wrote at add time (`--parent`, `--notify-box`), not proof.

Do not combine `--stack` and `--ws` in where. who reads the daemon table, not parent directories. With $AOS_KERNEL set (and no --daemon), who, ls, where and state first send {"procs_state_path": true} to $AOS_KERNEL and read the table file named in the reply; no reply within --timeout-s (default 3) = KernelFailed, with no fallback to $AOS_DAEMON. --daemon D reads that daemon directly.
