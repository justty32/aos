← [入口](README.md)｜涵蓋：改裁後的 help 草稿（英文；取代 [03](03-help草稿.md)）｜上一份 [04-改裁後設計](04-改裁後設計.md)

# help 草稿（照使用者 Q1～Q4 的答案＋甲級全做之後）

前提：N1～N4 都照推薦（N1、N2 不影響命令列；N3 選 B 就把 `--replace` 換回 `--override`；N4 選 B 就改 `call` 那句）。`XXX` 照舊不動。

## `aos-tools --help`

```
aos-tools - keep the list of tools an agent can call

usage: aos-tools [--file F] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-tools SUBCOMMAND --help

The list is one JSON file, the registry (default: ./tools.json). A tool is a folder
with _tooldef.json, a JSON file with a _tooldef key, or an executable that answers
--tooldef. Agents read the list before each thought and call tools through it.

A registry may carry one line, "override": OTHER_FILE. It then holds only the
differences from OTHER_FILE (which may override another file in turn). Each agent's
own additions and removals are kept this way.

subcommands:
  add XXX          put a tool on the list (XXX = folder, JSON file or executable)
  rm XXX           take it off the list (XXX = name, else path; tool files are kept)
  ls               show the list
  get XXX          print one tool's definition as JSON (XXX = name, else path)
  call NAME [JSON] run a tool once
  override BASE    make F a list of differences on top of BASE

examples:
  aos-tools add tools/clock                     # name = clock
  aos-tools add --name now tools/clock          # pick the name
  aos-tools add "$AOS_PROTO8/lib/base/bash"     # the shell expands it now
  aos-tools add --path-json '{"$env":"AOS_PROTO8","$path":"/lib/base/bash"}'
                                                # looked up on every use instead
  aos-tools ls -l
  aos-tools call clock '{"tz": "Asia/Taipei"}'

flags (before or after the subcommand):
      --file F   the registry to read and write (default: ./tools.json;
                 missing = no tools). add / rm write only F, never what it overrides.
  -h, --help     show this help

Relative paths are stored relative to the file they are written in, so a registry
and its tools can move together.

exit codes: 0 ok; 1 error ("aos-tools: error: CODE reason" on stderr);
            call returns the tool's own code (killed by signal N = 128+N).
more: proto8/cmd/aos-tools/README.md
```

## `aos-tools add --help`

```
aos-tools add - put a tool on the list

usage: aos-tools [--file F] add [--name N] [--replace] [--no-cache]
                 [--env-file FILE] [--envs K=V]... (XXX | --path-json JSON)

XXX is a tool folder, JSON file or executable. It is stored the way you give it:
absolute stays absolute; relative (to the current directory) is stored relative to
F. --path-json stores the JSON as given - a path string or a directive such as
{"$env": "AOS_PROTO8", "$path": "/lib/base/bash"} - and it is resolved on every use.

Prints: added NAME -> ABSOLUTE_PATH (FILE_WRITTEN: STORED_VALUE)

flags:
  -n, --name N        list it under this name (default: the folder name, or the file
                      name without extension; only A-Z a-z 0-9 _ -, at most 64)
      --replace       replace a tool already listed under that name
      --path-json J   store this JSON path value instead of XXX
      --envs K=V      set K to V for every call of this tool (repeatable; V is stored
                      as typed in F - not for secrets)
      --env-file FILE remember where FILE is (stored like XXX); it is read on every
                      call, never copied into F. Use it for secrets.
      --no-cache      ask the executable for its definition every time
  -h, --help          show this help

On a call, later wins: the tool's own .env (fills gaps only), the caller's
environment, --env-file, --envs.
A tool that declares variables you have not set gives a warning; add still succeeds.

exit codes: 0 added; 1 error (PathMissing, ToolDefMissing, ToolDefBad, NameBad, ToolExists...).
```

## `aos-tools rm --help`

```
aos-tools rm - take a tool off the list

usage: aos-tools [--file F] rm XXX

A listed name wins. Otherwise XXX is read as a path, and every name that points
there is removed. When the tool comes from a file that F overrides, F records the
removal and that file is left alone. Prints one line per name: removed NAME (F).
The tool's own files are never deleted.

flags:
  -h, --help   show this help

exit codes: 0 removed; 1 error (ToolMissing, RegistryBad, WriteFailed...).
```

## `aos-tools ls --help`

```
aos-tools ls - show the list

usage: aos-tools [--file F] ls [-l] [--json]

One line per tool, sorted by name: NAME TAB KIND TAB PATH (absolute).
KIND is dir (folder), json (JSON file) or exe (executable). Every tool is checked;
one broken tool is an error that names it. Executables are asked with --tooldef
(answers are cached in $AOS_STACK/tooldef_cache.json when AOS_STACK is set).

flags:
  -l             also show FROM (the file and key it comes from), STORED (the path
                 as written there) and ENV (variable names and the env file; never values)
  -j, --json     one JSON array with name, kind, path, tooldef and optional metainfo
  -h, --help     show this help

exit codes: 0 listed; 1 error (RegistryBad, PathMissing, ToolDefMissing, ToolDefBad...).
```

## `aos-tools get --help`

```
aos-tools get - print one tool's definition as JSON

usage: aos-tools [--file F] get XXX

A listed name wins; otherwise XXX is read as a path. Prints one JSON object per
match: name, kind, path, tooldef and optional metainfo. Variable values are not
printed (see ls -l).

flags:
  -h, --help   show this help

exit codes: 0 printed; 1 error (ToolMissing, RegistryBad, ToolDefBad...).
```

## `aos-tools call --help`

```
aos-tools call - run a tool once

usage: aos-tools [--file F] call NAME [ARGS_JSON]
       echo ARGS_JSON | aos-tools [--file F] call NAME

The tool gets ARGS_JSON on its stdin (given on the command line, or read from
stdin when omitted); its stdout is the result. The variables registered with add
are set for the call; a registered env file is read now, and a missing one is an
error. The tool runs through aos-exec in its own scratch folder:
$AOS_STACK/tools/NAME/ when AOS_STACK is set, otherwise aos-exec's default
(.stack/ in the current directory).

flags:
  -h, --help   show this help

exit codes: the tool's code (killed by signal N = 128+N);
            1 with "aos-tools: error:" on stderr = aos-tools itself failed.
```

## `aos-tools override --help`

```
aos-tools override - make F a list of differences on top of another registry

usage: aos-tools --file F override (BASE | --path-json JSON)

Writes "override": BASE into F (creating F when missing). From then on F shows
everything in BASE, plus what you add to F, minus what you rm from F. BASE is
stored like a tool path: absolute stays absolute, relative is stored relative to F,
--path-json is stored as given and resolved on every use. BASE may itself override
another file.

flags:
      --path-json J   store this JSON path value instead of BASE
  -h, --help          show this help

exit codes: 0 written; 1 error (RegistryBad when F already lists tools of its own
            without override, PathMissing, WriteFailed...).
```

## `aos-agent tools`（連帶）

```
aos-agent tools add - add a tool for this agent only

usage: aos-agent [--daemon D] tools [--target NAME] add [--replace] [--no-cache] NAME PATH

Written to this agent's own registry in its stack, which overrides the
definition's; the definition stays as it is. The first add or rm creates that file.
```

`aos-agent tools add` 的 `NAME PATH` 寫法與旗標補齊（第一輪的乙4）這次沒有被裁，照舊不動；`ls`／`get` 開頭那行 note 改成印「用的是哪一份、它 override 誰」。
