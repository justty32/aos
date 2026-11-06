# Registering and calling tools

Use aos-tools to edit a registry and call a registered tool with JSON on stdin.

```sh
aos-tools --file tools.json add --name read ../lib/base/read
aos-tools --file tools.json ls --json
printf '%s' '{"path":"a.txt"}' | aos-tools --file tools.json call read
aos-tools --file tools.json rm read
```

The default registry is `./tools.json`; a missing registry means no tools. `--file` and `--overlay` go before the subcommand. With an overlay, add/rm change only that overlay.

add accepts a folder, JSON file or executable. Paths resolve from cwd. Main registry paths are stored as absolute; overlay paths are stored relative to the overlay file. It prints one line `added NAME -> PATH`. `--name` overrides the default file/folder name. A duplicate gives `ToolExists`; `--override` replaces it. `--no-cache` is for executable tool definitions only.

rm matches a registered name first, otherwise a path. It removes all matches and prints `removed NAME` for each; files remain. ls prints NAME TAB KIND TAB PATH; `--json` prints an array with tool definitions. get prints matching definitions as JSON objects. Broken registered tools are errors.

11-06 note: Folder, JSON and executable tools receive the JSON unchanged on stdin through aos-exec. Only aos-tools call assigns the scratch stack: with a parent `$AOS_STACK`, the child gets `<parent>/tools/<registered-name>/`; otherwise aos-exec supplies its default. Callers pass their own stack. Registry env cannot override the scratch stack. See [J3 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).

call returns the tool's exit code (signal N = 128+N). A nonzero exit with `aos-tools: error:` means aos-tools failed; without that line, it is the tool's code.
