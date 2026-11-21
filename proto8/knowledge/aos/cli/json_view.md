# aos-json-view: print JSON in a layout a person can read

Read only: it prints one JSON file, or one part of it, and changes nothing. It is for a person at a terminal; inside aos use `json_get` / `json_ls`, which give exact JSON.

```sh
aos-json-view cfg.json                      # the whole file
aos-json-view cfg.json#/states/think        # one part; or as a second word: aos-json-view cfg.json '#/states/think'
aos-json-view --depth 1 --no-color cfg.json | less
```

What it prints: objects as `key: value` lines with aligned keys; short objects and arrays on one line (`{a: 1, b: x}`, `[a, b]`); longer arrays one item per line after `- `. Each indent level is `| `. Strings have no quotes (except an empty string, shown as `""`, and inside a one-line `{}` / `[]` a string with `,`, `: `, brackets or leading/trailing spaces), a `\n` in a string starts a new line, and a longer array of strings is shown as one text, one element per line. A `$ref` value is shown as `-> target` and is not followed. With a pointer the first line is `# FILE#/POINTER`. The output is not JSON: do not parse it or paste it back into a file.

- `--depth N`: expand only N levels; deeper ones show as `{…3 keys}` / `[…5 items]`. Arrays of strings are text and are never folded.
- `--width N`: wrap width (a number below 20 is taken as 20). Default: the terminal width; when stdout is not a terminal, `$COLUMNS`, else 100.
- `--color` / `--no-color`: colour is on by default only when stdout is a terminal and `NO_COLOR` is not set. Both together = `ArgumentsBad`.
- Flags may stand before or after FILE. A file really named `x#y` that exists is read as that file, not as a pointer.

Errors (`aos-json-view: error: CODE reason` on stderr, exit 1): `FileBad` (the file cannot be read, also when it does not exist, or it is not JSON), `PointerBad` (nothing at that pointer, or it does not start with `#/`), `ArgumentsBad` (no file, an extra word, `--depth` or `--width` not a positive number), `FlagUnknown`.
