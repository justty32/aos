# Function growth

Preview function moves with aos-grow; real runs rewrite config and can move or delete files.

```sh
aos-grow --dry-run up --to dir --name think --take brain.py fsm.json#/states/think/exec
aos-grow up --to file --name idle fsm.json#/states/idle/exec    # writes idle.json; the slot becomes "idle"
aos-grow --dry-run down fsm.json#/states/idle/exec             # back to inline; would remove idle.json
```

CALLER names the config slot that says what to run. up moves an inline instruction to NAME.json (`--to file`) or NAME/_entry (`--to dir`) and changes the slot to "NAME"; `--to` is required. up on a slot that is already `NAME` (with `NAME.json` beside it) moves `NAME.json` to `NAME/_entry`; this needs `--to dir`. down shrinks a folder containing only _entry to a file, or a file to inline; the slot must be exactly a name. Shared targets cannot shrink to inline. Relative references are rewritten to point to the same places.

`--name` (`-n`) is the new name; by default it is the slot's own name (`.../states/think/exec` gives `think`), and a slot like `/exec` needs `--name`. `--dry-run` goes before or after up/down and writes nothing. `--take` repeats, is only for `--to dir`, and must name a path in the instruction; the file must sit in the config file's folder. `TargetBad` or `NameBad` needs a corrected target/name, not a blind retry. Other codes: `CfgMissing`, `CfgBad`, `WriteFailed`, `CommandUnknown` (see aos/errors.md). More flags: run `aos-grow up --help`. Code that reads AOS_CF/AOS_CD/AOS_CO itself may observe changed locations.
