# Tool view

Look into one file step by step. The answer is one JSON object.

- JSON file: one level at `pointer` (empty = the whole file). A small value (up to 1000 characters as JSON) comes whole in `value`. A string over 80 characters comes as `counter_chars` and `head` (its first 60). A big object or array comes as `children` (key and type of each, plus its size: `counter_keys`, `counter_items`, or `counter_chars` and `head` for a long string; a short plain value gives `value` itself; the first 200, `counter_children_more` says how many more) plus a `hint`: add a child key to `pointer` and call again.
- Text file: a small one (up to 200 lines and 8KB) comes whole in `text`. A big one first gives an `outline` (Python class and def, Markdown headings, with line numbers; other files, or an empty outline: the first 40 lines as `head`; a Python syntax error adds `syntax_error`). Then ask for the lines you need with `start` and `end`.

Use it for a file you do not know yet, or a big one. Use `read` to read text in order, `json_ls` to list the keys at one JSON place, `json_get` for one value, `stat` for size and type only.

Examples with real output: `aos/tools/view.md#/view: examples`. Errors: `aos/tools/view.md#/view: errors`.

# view: examples

A big Markdown file gives an outline:
```json
{"path": "doc.md"}
```
-> `{"path":"doc.md","format":"markdown","counter_lines":303,"outline":[{"line":1,"level":1,"name":"Title"},{"line":3,"level":2,"name":"Part"}],"hint":"use start/end (line numbers) to view the part you need"}`

Then a range of lines:
```json
{"path": "doc.md", "start": 1, "end": 2}
```
-> `{"path":"doc.md","format":"text","counter_lines":303,"start":1,"end":2,"text":"# Title\ntext\n"}`

One level of a JSON file:
```json
{"path": "cfg.json", "pointer": "/states"}
```
-> `{"path":"cfg.json","format":"json","pointer":"/states","type":"object","counter_keys":2,"value":{"think":{"next":"act"},"act":{"next":"think"}}}`

With `start` or `end` (whole numbers from 1), `pointer` is ignored and any file (JSON too) is shown as lines. One range is at most 2000 lines or 50KB; if cut, `hint` says `use start=N to continue`.

# view: errors

- `FileMissing`: no such file. `FileBad`: a folder (use `ls`), a binary file, or `pointer` on a file that is not JSON (use `start` and `end`).
- `PointerMissing`: the key is not there; the reason names it. Go one level up and look at `children`.
- `ArgumentsBad`: also `pointer` not starting with `/`, or `start` past the end of the file.
- `ReadFailed`, `WsMissing`: `aos/errors/common.md#/Codes from file work`. Wrong or unknown keys (`ArgumentsBad`): `aos/errors/common.md#/Codes about what you gave`.
