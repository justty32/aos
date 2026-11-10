← [入口](README.md)｜涵蓋：照推薦全做之後的 help 草稿（英文）｜上一份 [02-改法](02-改法.md)

# help 草稿（照六題推薦與甲級全做之後）

程式輸出一律英文（11-05）。前提：Q1＝A（沒有 `--env-file`）、Q2＝A（沒有快取與 `--no-cache`）、Q3＝A（`--path-env`）、Q4＝A、Q6＝A。哪一題選了別的，對應的行照 [02](02-改法.md) 換回去。

## `aos-tools --help`

```
aos-tools - keep the list of tools an agent can call

usage: aos-tools [--file F] [--overlay O] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-tools SUBCOMMAND --help

The list is one JSON file, the registry (default: ./tools.json). A tool is a folder
with _tooldef.json, a JSON file with a _tooldef key, or an executable that answers
--tooldef. Agents read the list before each thought and call tools through it.

subcommands:
  add PATH            put a tool on the list
  rm NAME_OR_PATH     take it off the list (the tool's files are kept)
  ls                  show the list
  get NAME_OR_PATH    print one tool's definition as JSON
  call NAME [JSON]    run a tool once

examples:
  aos-tools add tools/clock                     # name = clock
  aos-tools add --name now tools/clock          # pick the name
  aos-tools add --path-env AOS_PROTO8/lib/base/bash
  aos-tools ls -l
  aos-tools call clock '{"tz": "Asia/Taipei"}'

flags (before or after the subcommand):
      --file F      the registry to use (default: ./tools.json; missing = no tools)
      --overlay O   one agent's own additions and removals on top of F; add / rm
                    then write only O. Usually reached through "aos-agent tools".
  -h, --help        show this help

Relative tool paths are stored relative to the registry file, so the registry and
its tools can move together.

exit codes: 0 ok; 1 error ("aos-tools: error: CODE reason" on stderr);
            call returns the tool's own code (killed by signal N = 128+N).
more: proto8/cmd/aos-tools/README.md
```

## `aos-tools add --help`

```
aos-tools add - put a tool on the list

usage: aos-tools add [--name N] [--override] [--envs K=V]... PATH
       aos-tools add [--name N] [--override] [--envs K=V]... --path-env VAR[/SUBPATH]
       (--file F / --overlay O: see aos-tools --help)

PATH is a tool folder, JSON file or executable. It is stored the way you give it:
absolute stays absolute; relative (to the current directory) is stored relative to
the registry file. --path-env stores "the value of VAR, plus SUBPATH", looked up
again on every use.

Prints: added NAME -> ABSOLUTE_PATH (FILE_WRITTEN: STORED_VALUE)

flags:
  -n, --name N       list it under this name (default: the folder name, or the file
                     name without extension; only A-Z a-z 0-9 _ -, at most 64)
      --override     replace a tool already listed under that name
      --envs K=V     set K to V for every call of this tool (repeatable; V is stored
                     as typed, in the registry file - not for secrets)
      --path-env VAR[/SUBPATH]
                     take the path from environment variable VAR instead of PATH
  -h, --help         show this help

Secrets: put them in a .env file next to the tool (read on every call), or export
them where the agent runs.
A tool that declares variables you have not set gives a warning; add still succeeds.

exit codes: 0 added; 1 error (PathMissing, ToolDefMissing, ToolDefBad, NameBad, ToolExists...).
```

## `aos-tools rm --help`

```
aos-tools rm - take a tool off the list

usage: aos-tools rm NAME_OR_PATH
       (--file F / --overlay O: see aos-tools --help)

A listed name wins. Otherwise it is read as a path, and every name that points
there is removed. Prints one line per name: removed NAME (FILE_WRITTEN).
The tool's own files are never deleted.

flags:
  -h, --help   show this help

exit codes: 0 removed; 1 error (ToolMissing, RegistryBad, WriteFailed...).
```

## `aos-tools ls --help`

```
aos-tools ls - show the list

usage: aos-tools ls [-l] [--json]
       (--file F / --overlay O: see aos-tools --help)

One line per tool, sorted by name: NAME TAB KIND TAB PATH (absolute).
KIND is dir (folder), json (JSON file) or exe (executable). Every tool is checked;
one broken tool is an error that names it. Executables are run with --tooldef.

flags:
  -l             also show FROM (file and key it comes from), STORED (the path as
                 written there) and ENV (names of the variables set; never values)
  -j, --json     one JSON array with name, kind, path, tooldef and optional metainfo
  -h, --help     show this help

exit codes: 0 listed; 1 error (RegistryBad, PathMissing, ToolDefMissing, ToolDefBad...).
```

## `aos-tools get --help`

```
aos-tools get - print one tool's definition as JSON

usage: aos-tools get NAME_OR_PATH
       (--file F / --overlay O: see aos-tools --help)

A listed name wins; otherwise it is read as a path. Prints one JSON object per
match: name, kind, path, tooldef and optional metainfo. Variable values are not
printed (see ls -l for their names).

flags:
  -h, --help   show this help

exit codes: 0 printed; 1 error (ToolMissing, RegistryBad, ToolDefBad...).
```

## `aos-tools call --help`

```
aos-tools call - run a tool once

usage: aos-tools call NAME [ARGS_JSON]
       echo ARGS_JSON | aos-tools call NAME
       (--file F / --overlay O: see aos-tools --help)

The tool gets ARGS_JSON on its stdin (given on the command line, or read from
stdin when omitted) and its stdout is the result. Variables stored with
add --envs are set for the call. The tool runs through aos-exec with its own
scratch folder: $AOS_STACK/tools/NAME/ when AOS_STACK is set, otherwise aos-exec's
default (.stack/ in the current directory).

flags:
  -h, --help   show this help

exit codes: the tool's code (killed by signal N = 128+N);
            1 with "aos-tools: error:" on stderr = aos-tools itself failed.
```

## `aos-agent tools add --help`（Q4＝A 連帶）

```
aos-agent tools add - add a tool for this agent only

usage: aos-agent [--daemon D] tools [--target NAME] add [--name N] [--override]
                 [--envs K=V]... (PATH | --path-env VAR[/SUBPATH])

Same as aos-tools add, written to this agent's own additions; the definition's
tool list stays as it is. See aos-tools add --help for the flags.
```
