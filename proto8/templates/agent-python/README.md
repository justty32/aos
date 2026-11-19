Look things up in the workspace and answer by mail (agent-python skeleton: an agent definition written as one agent.py).

This folder is one working agent definition. Everything in it except this README is made from **`agent.py`**: you change `agent.py`, run one command, and the other files are written for you. You do not `mkdir` or edit the JSON files one by one.

## Make your own agent from it

```sh
# copy the skeleton (or: agent_def with {"op": "new", "template": "agent-python", "path": "my_agent"})
cp -r $AOS_HOME/templates/agent-python my_agent
cd my_agent
# change the part of agent.py under "# ---- your agent", then:
python3 agent.py --defs          # optional: print what would be written, write nothing
python3 agent.py --write-defs    # write the definition files into this folder
aos-agent ctl add .              # mount it (add -d DAEMON, -w WORKSPACE as usual)
```

Keep the lines above `# ---- your agent` as they are: they find the `aos` package (an `aos/` folder next to `agent.py`, then `$AOS_HOME/lib`). Keep the last line `ag.main(...)`.

## Read this before you run --write-defs

1. **It overwrites, as a whole, every file `agent.py` declares**, every time, without asking. If you run it in a folder that already has hand-written `tools.json`, `fsm.json`, `system.txt` and so on, those are replaced. Look first with `python3 agent.py --defs`, or commit first. A file you want to keep writing by hand: declare it with `ag.by_hand("file name")`.
2. **Changes made directly in the generated files are gone at the next `--write-defs`.** That includes changes made by `agent_def tools` / `llm` / `system` or by an editor. Like a C compiler and its `.o` files: after it writes them, the files are ordinary definition files that anyone may change, and nothing remembers what was written. To keep a change, put it in `agent.py`.
3. **Renaming or removing a state of `FSM` can stop a running agent** that is sitting in that state (its `stage.txt` names a state that is no longer in `fsm.json`; aos-fsm then fails with `StateUnknown`). Rename states only when no agent using this definition is running.

What it does not touch: `_metainfo.json` keeps every key `agent.py` does not set (for example `lineage`, written by `agent_def new`); `README.md` is written only when it is missing (one line: `DESCRIPTION`); any other file in the folder is left alone, also files an older `agent.py` wrote but the current one no longer declares (delete those yourself). Nothing in the folder marks it as generated: delete `agent.py` and it is a plain definition.

## Files

| file | what it is | made from |
|---|---|---|
| `agent.py` | the source of this definition | you |
| `_entry` | mounts the agent on a daemon (`aos-agent ctl add`) | always written |
| `body.json` | runs the loop: `aos-loop loop.json` | always written |
| `loop.json` | runs `fsm.json` every 300 ms; names the ctl, state and state flux files | always written |
| `fsm.json` | the state machine | `FSM` |
| `interfaces.json` | names the other files (`entry`, `tools`, `llm`, `llm_keys`, `history`, `system`) | always written; `INTERFACES` is laid over it |
| `tools.json` | the tools | `TOOLS` |
| `llm.json` | brain settings | `LLM` |
| `system.txt` | the system text | `SYSTEM` |
| `_metainfo.json` | `summary` and `META` keys | `DESCRIPTION`, `META` |
| `README.md` | this file | written only when missing |
| `hooks.json` (not in this skeleton) | the hooks | `HOOKS` |
| any other name (not in this skeleton) | as given | `FILES` |

## What you write in agent.py

- `DESCRIPTION`: one English sentence: what the agent does. It becomes `summary` in `_metainfo.json`.
- `SYSTEM`: the system text as a string, or `ag.by_hand("system.txt")` to keep writing that file yourself.
- `TOOLS`: a list of
  - `std.pack("look")`: the tools of a pack of `std`, the library that comes with aos (`$AOS_HOME/lib/packs/look.json`). The pack is read when `agent.py` runs and its tools are written into `tools.json` one by one (no `$override`), so a tool added to the pack later shows up after the next `--write-defs`;
  - `std.tool("base/read")`: one tool of `std` (`$AOS_HOME/lib/tools/base/read`), named after its folder (`name="..."` picks another name);
  - `ag.tool("read", ag.home("/lib/tools/base/read"))`: one tool by its path; it replaces a tool of the same name from the packs. The path can also be a library tool: `ag.tool("read", my.tool("read"))`;
  - `ag.no("shell")`: take one tool out of the packs;
  - the `.pack(...)` / `.tool(...)` of another library (see "Libraries" below).
  - `std.pack(...)` and the `.pack(...)` of a library also take `prefix="..."` (put before every tool name), `rename={"read": "cat"}` (the name of one tool, instead of prefix + its name) and `exclude=["grep"]` (leave tools out).
  - When two packs give the same name and the tools are not exactly the same, `--write-defs` stops with `SpecBad` instead of letting one hide the other. Use `prefix=`, `rename=`, `exclude=`, or pick one with `ag.tool(name, ...)`.
- `LLM`: a dict. `{}` = the llm kernel's default brain; `{"model": "luna"}` picks a brain pack of the kernel. Other keys must be in `llm_keys` (`temperature`, `max_tokens`, ...).
- `FSM`: `std.fsm()` borrows the four cells of the `agent-fsm` template (`idle`, `think`, `wait`, `act`; the cell programs stay in `$AOS_HOME/templates/agent-fsm/`). Your own machine:

  ```python
  def cell(name):
      return ["python3", ag.home("/templates/agent-fsm/%s.py" % name)]

  FSM = ag.fsm("idle", [
      ag.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
      ag.state("think", cell("brain"), {0: "wait", 10: "idle"}),
      ag.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
      ag.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
  ])
  ```

  `next` maps an exit code (0-255, or `"*"` for any other) to the next state; every state needs `0` or `"*"`.
- Optional, passed as `ag.main(..., meta=META, interfaces=INTERFACES, hooks=HOOKS, files=FILES)`:
  - `META`: more keys for `_metainfo.json`, like `{"cost": {"time_ms": 60000}, "resource": ["llm"]}`;
  - `INTERFACES`: laid over the default `interfaces.json`, like `{"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}` (`None` removes a default key);
  - `HOOKS`: writes `hooks.json`, adds `"hooks": "hooks.json"` to `interfaces.json` and the `on_start` / `on_stop` lines (they fire `after_start` / `after_stop`) to `loop.json`. Write it as
    - a dict `{hook name: entry}`, the entries as in any `hooks.json` (`event`, `handler`, `condition`, `every_ms`, `config`, ...);
    - `std.hooks()`: the hooks of the `agent-fsm` template (`std.hooks("eca-claude")` / `("eca-pi")` for those); they are read from `$AOS_HOME/templates/<template>/hooks.json` and copied in, so the next `--write-defs` follows a changed template;
    - a list of those, laid one over the other (a later entry with the same name wins, `None` drops one): `HOOKS = [std.hooks(), {"timer": None, "mine": {...}}]`;
    - or `ag.by_hand("hooks.json")`.
  - `FILES`: other files written as they are, like `{"ladder.json": {...}}` (a dict or list is written as JSON, a string as it is). The name is one file in this folder; it cannot be a file that agent.py, the skeleton or the running agent writes.

## Without FSM (eca bodies: Claude Code, pi)

An eca definition has no state machine: its skeleton (`_entry`, `loop.json`, `cli.json`, `screen/`, `interfaces.json`) comes from its template. Copy the template first, put an `agent.py` in it, and leave `FSM` out:

```python
ag.main(DESCRIPTION, SYSTEM, TOOLS, LLM, hooks=HOOKS)      # no FSM
```

Then `--write-defs` writes only the content files (`SYSTEM`, `TOOLS`, `LLM`, `HOOKS`, and `FILES`, `META`) under the names the folder's `interfaces.json` gives, and checks `LLM` against its `llm_keys` (eca: `model` only). The skeleton is not touched; `INTERFACES` cannot be used. A folder without `interfaces.json`, or one that declares no file for something you declare, gets one `DefBad` line and nothing is written.

Paths: write paths outside this folder as `ag.home("/...")` (under `$AOS_HOME`) or `ag.env("AOS_WS", "/...")`; they are written as `{"$env": ..., "$path": ...}` and work on any machine and after any copy. Do not write `../` paths: they break when the folder is copied somewhere else.

`agent.py` is ordinary Python: use loops and small functions to build the lists. It should not use the network or read files outside this folder, apart from what the libraries read (packs, tool folders, `std.hooks`).

## Libraries

A library is a folder of a fixed shape: `packs/<name>.json` (tool packs, like `$AOS_HOME/lib/packs`) and `tools/<folder>/` (tools). `std` comes with aos (`std = ag.std`); its root is `$AOS_HOME`, with its packs in `lib/packs`, its tools in `lib/tools` and its hooks and state machine cells in `templates/`. Declare another library with its root, an absolute path or a directive:

```python
my = ag.lib("my", ag.env("AOS_WS", "/lib/my"))      # the name "my" is only for this agent.py
TOOLS = [std.pack("look"), my.pack("look")]          # the brain sees read, ls, ... and my_read
```

- The tools of another library get the library name and `_` in front (`my_read`); the tools of `std` keep their short names (`read`). The brain allows only letters, digits, `_` and `-` in a tool name.
- `tools.json` holds only full paths (`{"$env": "AOS_WS", "$path": "/lib/my/tools/read"}`), never the library name. A path written relative in a library's pack (`"../tools/read"`) is rewritten under the library root; it cannot leave the root.
- The root must be readable when `agent.py` runs: a variable that is not set, or a root that is not a folder, is `SpecBad`. Running `agent.py` therefore needs `AOS_HOME`, and for a root under `$AOS_WS`, `AOS_WS` too.
- In this first step a library has packs and tools only; hooks and state machines come from `std`.

## When a declaration is wrong

`--write-defs` and `--defs` check everything first and write nothing when something is wrong. You get one line, for example:

```
my_agent: error: SpecBad state think: next state 'wiat' is not one of the states (idle, think, wait, act) (fix the declaration in agent.py)
```

Then check the folder as usual: `agent_def` with `{"op": "check", "path": "my_agent"}` should answer `{"problems": []}`.
