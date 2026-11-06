# Help and flag placement

Put each flag at the level that owns it, before that level's positional arguments.

Run `aos-agent --help`, then `aos-agent tools --help`, then `aos-agent tools add --help`. Each prints only its own level. Other commands also support `COMMAND SUBCOMMAND --help`. Help needs no live daemon or target.

Examples:

```sh
aos-agent --daemon /srv/d ctl state --target bob
aos-agent tools --target bob ls --json
aos-agent llm --target bob set endpoint=smart-high
aos-tools --file tools.json ls --json
aos-grow --dry-run up --to file config.json#/exec
aos-eca-screen --eca ../eca open --detach
```

`aos-agent tools ls --target bob` gives `FlagUnknown`. `--daemon` belongs before the top-level subcommand; tools/llm `--target` belongs before their action. ctl target flags belong after the action.

The nine shared short names have fixed meanings: `-h --help`, `-d --daemon`, `-t --target`, `-j --json`, `-n --name`, `-w --ws`, `-s --stack`, `-f --follow`, `-y --yes`. Only use a short name where that help lists it. `--file`, `--detach` and `--timeout-s` have no short name. `-s`/`-w` are not aliases for the switches in `ctl where`, or the path in `ctl who`.

Use separate tokens: `-t bob`. `-tbob` and `-jf` are unknown flags. Use `--` to end flags where supported: `aos-agent say -t bob -- -hello`. No subcommand gives `ArgumentsBad`; an unknown subcommand gives `CommandUnknown`.
