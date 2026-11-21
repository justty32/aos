# aos-feedback: say what was hard

Record what was hard about a command or tool, and score how comfortable it is for AIs. Feedback never changes the target. The store is `$AOS_FEEDBACK` (default: the repo's `wf/advices/feedback/`, found beside the `proto8` folder above the command).

```sh
aos-feedback add "aos-agent ctl add" "usage unclear" "show an example" --kind help --score 0.4 --by opus --model claude-opus
# aos-feedback: recorded .../aos-agent.jsonl
aos-feedback ls                    # aos-agent  2  2026-11-11T03:18:53.119Z
aos-feedback show aos-agent
aos-feedback score aos-agent --observed ledger.jsonl
```

The key is the first word's basename (`aos-agent ctl add` -> `aos-agent`). `--kind` is usage, help, errors, args or other (default `other`); `--score` is 0 to 1 (1 = comfortable). `--by` defaults to the folder name of `$AOS_CD`, else `unknown`; `--model` defaults to `unknown`; `--family` and `--tier` override the rater rule. Flags may go before or after the arguments. `score` prints JSON: the mean of the per-kind means that have scores (usage, help, errors, args; `other` is left out), times calls/(calls+errors+retries) when the `--observed` ledgers hold calls of it; with no such calls it is not multiplied; with calls but no scores it is calls/(calls+errors+retries) alone; with neither it is `null`. A missing ledger = `FileMissing`; a broken store file = `FileBad`; an empty `$AOS_FEEDBACK` = `ArgumentsBad`; no proto8 folder found = `PathMissing`; unknown subcommand = `CommandUnknown`. Inside aos the tool is `lib/tools/aos/feedback` (not in the default packs). More flags: run `aos-feedback --help`.
