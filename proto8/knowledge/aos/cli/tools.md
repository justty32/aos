# Registering and calling tools

Use aos-tools to edit a registry and call a registered tool with JSON on stdin.

```sh
aos-tools --file tools.json add --name read ../lib/tools/base/read
aos-tools --file tools.json ls --json
printf '%s' '{"path":"a.txt"}' | aos-tools --file tools.json call read
aos-tools --file tools.json rm read
```

# The registry

The default registry is `./tools.json`; a missing registry means no tools. `--file` goes before or after the subcommand. A registry may carry `"$override": OTHER_FILE` (or a list of files): it then holds only the differences from that file, later wins, and an entry whose value is `null` is not a tool. add/rm write only the `--file` registry, never the file it overrides. `aos-tools --file F override BASE` (or `--path-json JSON`) turns F into such a list of differences.

# add

add accepts a folder, JSON file or executable. Paths resolve from cwd. The stored path keeps the form you gave: an absolute path is stored absolute; a relative path is stored relative to the folder of the registry written. `--path-json JSON` stores a path string or directive as given, e.g. `{"$env": "AOS_HOME", "$path": "/lib/tools/base/shell"}` (set `AOS_HOME` once per machine); it is resolved on every use and never written back. A path that resolves to nothing gives `PathMissing` (get and call also name the registry field it came from). It prints one line `added NAME -> PATH (FILE: STORED)`. `--name` overrides the default file/folder name; a name is `[A-Za-z0-9_-]`, 64 characters at most (else `NameBad`). A duplicate gives `ToolExists`; `--replace` replaces it. Flags may go before or after the path. `--no-cache` is for executable tool definitions only.

# ls, get, rm

rm matches a registered name first, otherwise a path. It removes all matches and prints `removed NAME (FILE: key deleted)` for each (`set to null over BASE` when the overridden file has that name); files remain. ls prints NAME TAB the first sentence of its description (see one in full with get); `ls -l` prints NAME TAB KIND TAB PATH TAB FROM TAB STORED TAB ENV; `--json` prints an array with tool definitions; `-l` and `--json` together are `ArgumentsBad`. get prints matching definitions as JSON objects. A broken registered tool (path gone, definition missing or bad) does not stop ls: it gets one warning line naming it and how to fix it, ls shows `NAME TAB broken: CODE (...)` (KIND `broken` in `-l`), `--json` leaves it out, and ls exits 0. get NAME and call NAME on it fail with its own error (for example PathMissing). A registry file that is not JSON or has the wrong shape is still an error.

# call

`call NAME [ARGS_JSON]`: the arguments come from the second argument, or from stdin when it is left out. Every tool gets its JSON input unchanged on stdin. `aos-tools call` gives it a scratch stack: `<parent>/tools/<registered-name>/` when `$AOS_STACK` is set, otherwise aos-exec's default. A registry `env` cannot change that stack. With `$AOS_STACK` set, the tool also gets `AOS_STACK_IN_CALLER=tools/NAME` (where its folder sits in your stack), so a path it prints as `$AOS_STACK/tools/NAME/...` opens from your stack as written. The scratch folder is not created beforehand (aos-exec `--stack-lazy`); a tool that writes there creates it.

call returns the tool's exit code (signal N = 128+N). A nonzero exit with `aos-tools: error:` means aos-tools failed; without that line, it is the tool's code. To give the same tools to an external agent, use `aos-mcp` (`aos/cli/mcp.md`).

Other codes: `CommandUnknown`, `RegistryBad`, `ToolDefMissing`, `ToolDefBad`, `ToolMissing`, `DotenvBad`, `DirectiveBad`, `CommandMissing`, `WriteFailed` (see aos/errors.md). More flags: run `aos-tools SUBCOMMAND --help`.
