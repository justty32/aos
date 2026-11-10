# Registering and calling tools

Use aos-tools to edit a registry and call a registered tool with JSON on stdin.

```sh
aos-tools --file tools.json add --name read ../lib/base/read
aos-tools --file tools.json ls --json
printf '%s' '{"path":"a.txt"}' | aos-tools --file tools.json call read
aos-tools --file tools.json rm read
```

The default registry is `./tools.json`; a missing registry means no tools. `--file` and `--overlay` go before the subcommand. With an overlay, add/rm change only that overlay.

add accepts a folder, JSON file or executable. Paths resolve from cwd. Main registry paths are stored as absolute. With `--overlay`, paths are always stored relative to the overlay file's folder: a target inside it as a plain relative path; a target inside the aos repo's `proto8/` as `.aos-proto8/<path in proto8>`, where `.aos-proto8` is a machine-local symlink to that machine's `proto8/` created next to the overlay (kept out of git; after moving to another machine run `copy-out --relink <image root>`); any other target relative as well. Stored paths never hold a home folder or the repo's location. It prints one line `added NAME -> PATH`. `--name` overrides the default file/folder name. A duplicate gives `ToolExists`; `--override` replaces it. `--no-cache` is for executable tool definitions only.

rm matches a registered name first, otherwise a path. It removes all matches and prints `removed NAME` for each; files remain. ls prints NAME TAB KIND TAB PATH; `--json` prints an array with tool definitions. get prints matching definitions as JSON objects. Broken registered tools are errors.

11-06 note: Folder, JSON and executable tools receive the JSON unchanged on stdin through aos-exec. Only aos-tools call assigns the scratch stack: with a parent `$AOS_STACK`, the child gets `<parent>/tools/<registered-name>/`; otherwise aos-exec supplies its default. Callers pass their own stack. Registry env cannot override the scratch stack. See [J3 implementation](../../../thinking/2026-11/05/json-argv/10-J3到J7實作結果.md#j3-aos-tools-收口).

call returns the tool's exit code (signal N = 128+N). A nonzero exit with `aos-tools: error:` means aos-tools failed; without that line, it is the tool's code.
