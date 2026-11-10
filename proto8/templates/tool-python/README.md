# How to make a tool from this folder (tool-python skeleton)

This folder is one working tool. It adds two numbers. To make your own tool, change **only `tool.py`**, and only the part under `# ---- your tool`. Use `edit` on that part; do not write a new `tool.py` from scratch (the lines at the top load the helper, and the last line `ts.main(...)` runs your tool).

## Files

| file | what it is | do you edit it? |
|---|---|---|
| `tool.py` | the tool: description, parameters, `run` | **yes** |
| `_entry.json` | tells aos-exec to run `python3 tool.py` | no |
| `_tooldef.json` | what the model sees (made from `tool.py`) | no, it is generated |
| `_metainfo.json` | facts about the tool (made from `tool.py`) | no, it is generated |

After you change `tool.py`, run `tools_def` with `{"op": "check", "path": "<this folder>"}`. It remakes `_tooldef.json` and `_metainfo.json` from `tool.py` and tells you what is wrong. Then add the tool: `self_tools` with `{"op": "add", "path": "<this folder>"}`. You can call it from your next turn. Its name is the folder name.

## The four things you write in tool.py

1. `DESCRIPTION`: one string. What the tool does, plus one example written as `Example: {"a": 6, "b": 7} -> 42`. `tools_def` check runs this example and says `bad` if your tool gives something else, so make it true.
2. `PARAMS`: a list. One `ts.param(name, type, description)` per argument.
   - `type` is one of: `"string"`, `"integer"`, `"number"`, `"boolean"`, `"array"`, `"object"`.
   - Optional argument: add `default=...`, like `ts.param("times", "integer", "how many times", default=1)`.
   - Only some values allowed: `enum=["c", "f"]`.
   - List of strings: `ts.param("words", "array", "the words", items="string")`.
   - No arguments at all: `PARAMS = []`.
3. `META`: a dict. Write `{}` or only what is different from the defaults. Defaults: `side_effect` False (set True if the tool writes files or sends things), `deterministic` True (set False if the same input can give a different answer), `timeout_ms` 10000.
4. `def run(args):` gets a dict with your parameters (already checked: right types, required ones present, defaults filled in). Return the result:
   - a string is printed as is;
   - a number, dict or list is printed as JSON;
   - for an error, call `ts.fail("SomethingBad", "what went wrong")`. The code is one CamelCase word.

Keep the last line: `ts.main(run, DESCRIPTION, PARAMS, META)`.

## Full example: a tool that multiplies two numbers

Make the folder: `tools_def` with `{"op": "new", "path": "my_tools/mul"}`. Then change the part of `my_tools/mul/tool.py` under `# ---- your tool` to:

```python
DESCRIPTION = 'Multiply two numbers and return the product. Example: {"a": 6, "b": 7} -> 42'

PARAMS = [
    ts.param("a", "number", "the first number"),
    ts.param("b", "number", "the second number"),
]

META = {}


def run(args):
    return args["a"] * args["b"]


ts.main(run, DESCRIPTION, PARAMS, META)
```

Check it, and try it once: `tools_def` with `{"op": "check", "path": "my_tools/mul", "sample": {"a": 6, "b": 7}}`. The last lines say `ok    example: ... -> 42`, `ok    try: ... 42` and `stage 3 of 3`. Then `self_tools` with `{"op": "add", "path": "my_tools/mul"}`, and next turn call `mul` with `{"a": 6, "b": 7}`.

## What the tool does for you

- Wrong type, missing required key, unknown key, value not in `enum`: the tool answers `mul: error: ArgumentsBad ...` without calling `run`.
- If `run` crashes, the answer is `mul: error: RunFailed run() raised ZeroDivisionError: division by zero (tool.py line 33)`.
- `python3 tool.py --tooldef` / `--metainfo` print the generated JSON; `python3 tool.py --write-defs` writes the two files (this is what `check` runs).
- The lines above `# ---- your tool` find `tool_spec.py`: next to `tool.py`, then in a `lib/` above this folder, then in `$AOS_HOME/lib`. So the folder works anywhere when `AOS_HOME` is set.
