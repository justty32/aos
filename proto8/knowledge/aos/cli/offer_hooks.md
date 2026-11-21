# aos-hook: offer hook points from your own program

Use aos-hook when a program you write (C++, shell, anything that can start a process) should let others hook into it, the way an agent's hookeds.json hooks into an agent. Hooking into an existing agent is `aos-agent hook` instead (aos/cli/hook.md).

A hook point is one `aos-hook fire` at that moment. aos-hook only runs the handlers hooked on the event, in name order, and gives back each one's exit code and stdout; what they mean (block, change a field, a failure) your program decides. Those who hook in write a hookeds list:

```json
{"description": "What is hooked on before_save.",
 "a_deny": {"event": "before_save", "handler": "a_deny", "timeout_ms": 5000},
 "b_rename": {"event": "before_save", "handler": "b_rename"}}
```

```sh
echo '{"file": "notes.txt"}' | aos-hook fire --list hookeds.json --stack "$STATE" before_save
# {"event": "before_save", "hooks": [{"hook": "a_deny", "code": 0, "stdout": "", "error": null}, {"hook": "b_rename", "code": 0, "stdout": "{\"file\": \"notes.txt.bak\"}\n", "error": null}]}   exit 0
echo '{"file": "secret.txt"}' | aos-hook fire -q --stop-on-nonzero --list hookeds.json --stack "$STATE" before_save
# exit 10: a_deny said no (10 prints no error line); another non-zero code: that code and "aos-hook: error: HookFailed ..."
```

- Where the hooks are: `--list FILE` (repeatable; a later file overrides an earlier one by name, null turns a hook off, a missing file has no hooks) or `--def DIR` (the `hookeds` of DIR/interfaces.json, each relative one with the stack's same-named copy on top).
- An entry: `event`, `handler` (a path relative to the list's folder, or a directive), `timeout_ms` (default 60000, 0 = no limit; at the limit the handler's whole process group is stopped). Other keys are kept for your program; aos-hook does not read them.
- The event data is only the JSON object on stdin (give JSON or /dev/null: aos-hook reads stdin to the end unless it is a terminal). Each handler gets the same data with `event`, `hook` and `stack` added, as `STACK/hookeds/NAME/event.json` on its stdin; its own `$AOS_STACK` is that folder. `--stack DIR` defaults to `$AOS_STACK`.
- stdout: one JSON line `{"event", "hooks": [{"hook", "code", "stdout", "error"}]}` (`code` null and `error` the reason when the handler timed out or could not start); `-q` prints nothing. Exit 0 whatever the handlers did; `--stop-on-nonzero` stops at the first non-zero code and exits with it (timed out / cannot start = 1). Errors (`aos-hook: error: CODE reason`, exit 1): `ArgumentsBad`, `HooksBad`, `InterfaceBad`, `StackMissing`, `HookFailed`.
- A declaration tells others what points you offer (only for reading; aos-hook and the engine never read it): a JSON object `hooks.json` whose keys are the point ids, each with a required `input` (a JSON Schema of what a handler gets) and any other keys you like (`description`, `output`, `block`, `phase`, `condition`...); a top-level `description` is a sentence, not a point. A definition names its declarations in `interfaces.json` (`"hooks": "hooks.json"` or an array of file names and directives).

```json
{"description": "Hook points of my-saver.",
 "before_save": {"description": "before a file is saved",
                 "input": {"type": "object", "properties": {"event": {"const": "before_save"}, "hook": {"type": "string"},
                           "stack": {"type": "string"}, "file": {"type": "string", "description": "the file name"}}},
                 "output": {"type": "object", "properties": {"file": {"type": "string", "minLength": 1}}},
                 "phase": "before", "block": true, "if_blocked": "the file is not saved"}}
```

- The aos-loop points (after_start, after_stop, before_run, after_run) are declared in `$AOS_HOME/lib/aos/apps/hook/loop_hooks.json`; a loop.json fires them with `aos-hook fire -q --stop-on-nonzero --def $AOS_CD EVENT`, so the handler's exit code reaches aos-loop as it is. Their handlers read `AOS_LOOP_*` from the environment (and an fsm agent's state from `STACK/stage.txt`).
- Each fire starts one Python process (tens of milliseconds) plus the handlers. A Python program runs handlers without that process: `aos.hook_run.fire(event, data, aos.hook_lists.load(paths), stack)`. More: `aos-hook --help`, `aos-hook fire --help`; an overview of the whole hook system for people (in Chinese): `$AOS_HOME/lib/aos/apps/hook/docs/README.md`.
