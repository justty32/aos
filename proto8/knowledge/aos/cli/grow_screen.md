# Function growth and ECA screens

Preview function moves with aos-grow; access an ECA screen through aos-agent when possible.

```sh
aos-grow --dry-run up --to dir --name think --take prompt.txt fsm.json#/states/think/exec
aos-grow --dry-run down fsm.json#/states/think/exec
```

CALLER names the config slot that says what to run. up moves an inline instruction to NAME.json or NAME/_entry and changes the slot to "NAME". down shrinks a folder containing only _entry to a file, or a file to inline. Shared targets cannot shrink to inline. Relative references are rewritten to point to the same places.

`--dry-run` goes before up/down and writes nothing. Review the plan: real runs rewrite config and can move or delete files. `--take` repeats and is only for `--to dir`. `TargetBad` or `NameBad` needs a corrected target/name, not a blind retry. Code that reads AOS_CF/AOS_CD/AOS_CO itself may observe changed locations.

`aos-eca-screen --eca ECA_DIR open --detach`, close and watch are the lower-level screen actions. `--eca` goes before the action; `--detach` goes after open and has no short name. They read AOS_STACK and AOS_WS. ECA_DIR contains cli.json.

open attaches unless detached; Ctrl-] (or Ctrl-\) leaves the screen running. close keeps the conversation and refuses while answering (`SessionBad`). watch ends after one answer, or when its daemon row stops running/disappears. If the daemon/table cannot be read, watch keeps waiting. Ctrl-C leaves watch with exit 0.
