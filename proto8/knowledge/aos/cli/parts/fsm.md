# aos-fsm: one step of a state table

```json
{"_entry": ["aos-fsm", {"$env": "AOS_CF"}], "start": "a", "states": {
 "a": {"exec": {"argv": ["sh", "-c", "echo in a"]}, "next": "b"},
 "b": {"exec": {"argv": ["sh", "-c", "echo in b; exit 3"]}, "next": {"3": "a", "*": "b"}}}}
```

```sh
AOS_STACK=/tmp/st aos-fsm fsm.json      # prints "in a"; /tmp/st/stage.txt is now b
AOS_STACK=/tmp/st aos-loop --max 3 fl.json   # fl.json: {"exec": "fsm.json"}: in a, in b, in a
```

The current state is in `$AOS_STACK/stage.txt` (none = `start`). `next` as a name = move only on exit 0; as an object = look up the exit code (`*` = any). Moved = exit 0. A code the table does not catch = the step's own code, state unchanged. No `AOS_STACK` = `StackMissing`. A `stage.txt` state that is not in the table = `StateUnknown`; a bad table = `CfgBad` (a `next` object needs `"0"` or `"*"`). The `_entry` key lets aos-exec and aos-loop run the table. An agent-fsm's `fsm.json` is such a table (idle, think, wait, act).
