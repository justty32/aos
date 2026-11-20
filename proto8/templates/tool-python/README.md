# How to make a tool from this folder (tool-python skeleton)

This folder is one working tool. It adds two numbers. To make your own tool, change **only `tool.py`**, and only the part under `# ---- your tool`. Use `edit` on that part; do not write a new `tool.py` from scratch (the lines at the top load `fn` from the `aos` package, and the last line `fn.main(...)` runs your tool).

## Files

| file | what it is | do you edit it? |
|---|---|---|
| `tool.py` | the tool: one Python function marked `@fn.tool` | **yes** |
| `_entry.json` | tells aos-exec to run `python3 tool.py` | no |
| `_tooldef.json` | what the model sees (compiled from `tool.py`) | no, it is compiled |
| `_metainfo.json` | facts about the tool (compiled from `tool.py`) | no, it is compiled |

After you change `tool.py`, run `tools_def` with `{"op": "check", "path": "<this folder>"}`. It recompiles `_tooldef.json` and `_metainfo.json` from `tool.py` and tells you what is wrong. Then add the tool: `self_tools` with `{"op": "add", "path": "<this folder>"}`. It works at once: call it by its name in your next reply. Its name is the folder name.

## What you write in tool.py

One function with `@fn.tool` on top, and the last line `fn.main(that function)`. The description and the parameters come from the function itself:

1. **The docstring** (the text right under `def`): what the tool does, plus one example written as `Example: {"a": 6, "b": 7} -> 42`. `tools_def` check runs this example and says `bad` if your tool gives something else, so make it true. Everything before the `Args:` line is the description.
2. **`Args:` in the docstring**: one line `name: what it is` per parameter (a deeper line goes on with the line above). Every parameter needs one.
3. **The parameters and their types**: `def mul(a: float, b: float):`. Every parameter needs a type: `str`, `int`, `float`, `bool`, `list`, `dict` (the model sees string, integer, number, boolean, array, object); `list[str]` is a list of strings.
   - Optional parameter: give it a default, like `times: int = 1`.
   - No parameters at all: `def now():`.
4. **`@fn.tool(meta={...})`**: only what is different from the defaults (or just `@fn.tool`). Defaults: `side_effect` False (set True if the tool writes files or sends things), `deterministic` True (set False if the same input can give a different answer), `timeout_ms` 10000 (0 = no limit).
5. **The body** gets the parameters already checked (right types, required ones present, defaults filled in). Return the result:
   - a string is printed as is;
   - a number, dict or list is printed as JSON;
   - for an error, call `fn.fail("SomethingBad", "what went wrong")`. The code is one CamelCase word.

Written out instead of taken from the function (both work; the written one wins, one parameter at a time): `@fn.tool(description="...", params=[fn.param("a", "number", "the first number", enum=[1, 2])], errors=["SomethingBad"])`. A parameter's required / default always comes from the `def` line.

Keep the last line: `fn.main(...)` with your function's name.

## Full example: a tool that multiplies two numbers

Make the folder: `tools_def` with `{"op": "new", "path": "my_tools/mul"}`. Then change the part of `my_tools/mul/tool.py` under `# ---- your tool` to:

```python
@fn.tool
def mul(a: float, b: float) -> float:
    """Multiply two numbers and return the product. Example: {"a": 6, "b": 7} -> 42

    Args:
      a: the first number
      b: the second number
    """
    return a * b


fn.main(mul)
```

Check it, and try it once: `tools_def` with `{"op": "check", "path": "my_tools/mul", "sample": {"a": 6, "b": 7}}`. The last lines say `ok    example: ... -> 42`, `ok    try: ... 42` and `stage 3 of 3`. Then `self_tools` with `{"op": "add", "path": "my_tools/mul"}`, and in your next reply call `mul` with `{"a": 6, "b": 7}`.

## What the tool does for you

- Wrong type, missing required key, unknown key, value not in `enum`: the tool answers `mul: error: ArgumentsBad ...` without calling your function.
- A missing description, type or parameter description: `mul: error: SpecBad ...` says what to add.
- If your function crashes, the answer is `mul: error: RunFailed mul() raised ZeroDivisionError: division by zero (tool.py line 33)`.
- `python3 tool.py --compile` compiles `tool.py` into the two files (this is what `check` runs); `python3 tool.py --dry-run` prints both and writes nothing; `--tooldef` / `--metainfo` print one of them. Compiling again overwrites both, so a change made directly in them is gone: change `tool.py` instead.
- The lines above `# ---- your tool` find the `aos` package (it holds `fn`): an `aos/` folder next to `tool.py`, then `$AOS_HOME/lib` (it no longer looks for a `lib/` above this folder). So the folder works anywhere when `AOS_HOME` is set; without it you get `HomeMissing`.
- An aos upgrade that changes `fn` does not touch the compiled files: run `check` (or `--compile`) again. A `.py` file registered as a tool by itself (aos-tools asks it `--tooldef`) is cached by that file's time and size, so the cache also stays as it was until the file changes.
