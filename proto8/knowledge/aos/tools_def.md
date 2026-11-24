# Making a new tool: tools_def

A tool is a location with three parts: an entry (what runs), `_metainfo` (what it says about itself: for reference, not rules; optional) and `_tooldef` (what the model sees). In a folder they are the files `_entry` or `_entry.json`, `_metainfo.json`, `_tooldef.json`; in a JSON object they are the keys `_entry`, `_metainfo`, `_tooldef`. `_tooldef` may also be written as a `tooldef` key inside `_metainfo`; `tools_def` check and `aos-tools` count either one, and when both exist the separate `_tooldef` wins on the same top-level key.

- Make a new tool from the Python skeleton and check it: `tools_def` (see `aos/tools_def.md#/tools_def`).
- Build one step by step (entry and a small script, then `_metainfo`, then `_tooldef`): `tools_def` add_entry, add_metainfo, add_tooldef.
- Write the tool as one Python function with `fn` (`@fn.tool` and `fn.main`; see `aos/tools_def.md#/fn (write a tool as one Python function)`).
- Add it to your own tools: `self_tools` with `{"op": "add", "path": "..."}` (see `aos/me/self_tools.md`).

# tools_def

One op per call:

- new: `{"op": "new", "path": "my_tools/mul"}` copies the skeleton (a working tool that adds two numbers) to a new folder. `path` must not exist yet; relative paths start at your workspace, absolute paths work anywhere you may write. Optional `"description"` fills in what the tool does. `path` may also be `FILE.json#/POINTER` (like `my_tools/box.json#/tools/mul`): the tool goes into that JSON object (`_entry`, `_tooldef`, `_metainfo` keys) and its script `mul.py` next to the JSON file; two tools can share one JSON file.
- check: `{"op": "check", "path": "my_tools/mul", "sample": {"a": 6, "b": 7}}`. One line per item: `ok`, `bad` (with how to fix), `made` (it recompiled `_tooldef.json` and `_metainfo.json` from `tool.py`), `note`, `example` (it runs the `Example: {...} -> result` written in the description and compares), `try` (one call with `sample`). The last line is the stage: `stage 3 of 3 ... a tool: add it with self_tools ...`. Any `bad` line ends the answer with `tools_def: error: ToolBad ...`.

Steps for a new tool:

1. `tools_def` new.
2. Change only the part of `tool.py` that new prints (the function under `@fn.tool`: its name, docstring, typed parameters and body) with `edit`; keep the lines above it. `README.md` in the skeleton has a full example.
3. `tools_def` check with a `sample`. Fix every `bad` line and check again.
4. `self_tools` `{"op": "add", "path": "my_tools/mul"}`. It works at once: in your next reply (this turn) call it directly by its name (the folder name, or the last part of the pointer), like any other tool.

`path` for check can also be a JSON file or `FILE.json#/POINTER` whose object has an `_entry` key (like `["python3", "tool.py"]`, run from the JSON file's folder). `self_tools` add takes all three: a folder, a JSON file or `FILE.json#/POINTER`.

Step by step, for a folder, a JSON file or `FILE.json#/POINTER` (each step says the stage after it; a part that is already there = `PathExists`):

1. `{"op": "add_entry", "path": "my_func"}` writes the entry (`_entry.json` in a folder, the `_entry` key in a JSON object) and puts a small Python script next to it (the skeleton's, unless `"script": "name.py"` is already there): now aos-exec can run it.
2. `{"op": "add_metainfo", "path": "my_func"}` writes `_metainfo`: from the script if it is written with `fn`, otherwise give `"description"` (and `"meta"`).
3. `{"op": "add_tooldef", "path": "my_func"}` writes `_tooldef`: from the script, or give `"description"` and `"params": [{"name": "a", "type": "number", "description": "the first number"}]`.

Errors: `ArgumentsBad`, `OpUnknown`, `PathExists` (pick another path), `PathMissing`, `FileBad`, `PointerMissing`, `MkdirFailed`, `WriteFailed`, `ToolBad`.

# fn (write a tool as one Python function)

In `tool.py`, below `# ---- your tool`:

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

- The docstring up to `Args:` is the description. Write the example as `Example: {...} -> result`: `tools_def` check runs it.
- `Args:` has one line `name: what it is` per parameter. Every parameter needs a type: `str`, `int`, `float`, `bool`, `list`, `dict` (string, integer, number, boolean, array, object), `list[str]` for a list of strings. With a default (`times: int = 1`) the parameter is optional.
- Missing description, type or parameter line = `SpecBad`, one line that says what to add.
- Written out instead (the written one wins, one parameter at a time): `@fn.tool(description="...", params=[fn.param("a", "number", "the first number", enum=[...], items="string")], errors=["CityMissing"], meta={...})`.
- `meta`: only what differs from the defaults (`side_effect` False, `deterministic` True, `timeout_ms` 10000 ...; 0 = no limit).
- The function gets checked arguments with defaults filled in. Return a string (printed as is) or a number, dict or list (printed as JSON). Error: `fn.fail("CityMissing", "no such city")`.
- Wrong arguments are `ArgumentsBad` before the function runs; a crash in it is `RunFailed` with the line number.
- `python3 tool.py --compile [LOCATION]` compiles `tool.py` and writes `_tooldef` and `_metainfo` (a folder gets two files; `FILE.json#/POINTER` gets two keys); `--dry-run` prints both as one JSON object and writes nothing; `--tooldef` / `--metainfo` print one of them.


In an agent.py, the same function can go straight into `tools=[..., add]` (and an `@fn.hook("before_tool", ...)` function into `hooks=[...]`): compiling pulls each one out into `fn/<name>.py` of the definition folder and points `tools.json` / `hookeds.json` at it. It may use only builtins, its own variables, `fn` and modules imported at the top of agent.py; relative paths in it start at `fn/`. See templates/agents/agent-python/README.md, "Functions as tools and hooks".
