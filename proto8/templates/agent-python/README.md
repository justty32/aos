Look things up in the workspace and answer by mail (agent-python skeleton: an agent definition written as one agent.py).

This folder is one working agent definition. **`agent.py` is its source; every other file here (except this README) is compiled from it**, the way a C compiler turns a `.c` file into a `.o` file. You change `agent.py`, run one command, and the JSON files are written for you; you do not `mkdir` or edit them one by one.

- **What compiling is.** `python3 agent.py --compile` runs `agent.py` and writes the definition files (`fsm.json`, `tools.json`, ...) into this folder. From then on aos runs those files, not `agent.py`: like a `.o` file, they no longer need their source.
- **Compiling again overwrites.** Recompiling writes every declared file again as a whole, without asking, so a change made directly in a compiled file is gone. Change `agent.py` and recompile instead.
- **Static and dynamic linking.** Some things are copied into the compiled files when you compile, like a library linked statically into a program: `std.hooks()`, everything taken from another `agent.py` with `defs.load`, and by default the tools of a pack (`std.pack`, a library's `.pack`). A change there shows up only after you recompile. Other things are only named in the compiled files and read when the agent runs, like a library linked dynamically (a `.so` loaded at start): the tool programs themselves, the state machine cells of `std.fsm()`, and the packs you link dynamically (`--dynamic`, see "Linking tool packs" below). A change there shows up at the agent's next start without recompiling.

## Make your own agent from it

```sh
# copy the skeleton (or: agent_def with {"op": "new", "template": "agent-python", "path": "my_agent"})
cp -r $AOS_HOME/templates/agent-python my_agent
cd my_agent
# change the part of agent.py under "# ---- your agent", then:
python3 agent.py --dry-run       # optional: compile and print what would be written, write nothing
python3 agent.py --compile       # compile: write the definition files into this folder
aos-agent ctl add .              # mount it (add -d DAEMON, -w WORKSPACE as usual)
```

Keep the lines above `# ---- your agent` as they are: they find the `aos` package (`$AOS_HOME/lib` first, then an `aos/` folder next to `agent.py`, so a file named `aos.py` next to it does not get in the way when `AOS_HOME` is set), then import `defs` with `from aos.py.agent import defs` (everything below is `defs.something`). Keep the last line `defs.main(...)`.

## Read this before you run --compile

1. **It overwrites, as a whole, every file `agent.py` declares**, every time, without asking. If you run it in a folder that already has hand-written `tools.json`, `fsm.json`, `system.txt` and so on, those are replaced. Look first with `python3 agent.py --dry-run`, or commit first. A file you want to keep writing by hand: declare it with `defs.extern("file name")`.
2. **Changes made directly in the compiled files are gone when you recompile.** That includes changes made by `agent_def tools` / `llm` / `system` or by an editor. Like a C compiler and its `.o` files: after it writes them, the files are ordinary definition files that anyone may change, and nothing remembers what was written. To keep a change, put it in `agent.py`.
3. **Renaming or removing a state of `FSM` can stop a running agent** that is sitting in that state (its `stage.txt` names a state that is no longer in `fsm.json`; aos-fsm then fails with `StateUnknown`). Rename states only when no agent using this definition is running.

What it does not touch: `_metainfo.json` keeps every key `agent.py` does not set (for example `lineage`, written by `agent_def new`); `README.md` is written only when it is missing (one line: `DESCRIPTION`); any other file in the folder is left alone, also files an older `agent.py` wrote but the current one no longer declares (delete those yourself). Nothing in the folder marks it as compiled: delete `agent.py` and it is a plain definition.

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
- `SYSTEM`: the system text as a string, or `defs.extern("system.txt")` to keep writing that file yourself (like `extern` in C: `agent.py` only names the file, which is defined elsewhere, by you; compiling neither writes nor overwrites it).
- `TOOLS`: a list of
  - `std.pack("look")`: the tools of a pack of `std`, the library that comes with aos (`$AOS_HOME/lib/packs/look.json`). The pack is read when `agent.py` runs and, linked statically (the default), its tools are written into `tools.json` one by one (no `$override`), so a tool added to the pack later shows up after you recompile (dynamic linking: see "Linking tool packs");
  - `std.tool("base/read")`: one tool of `std` (`$AOS_HOME/lib/tools/base/read`), named after its folder (`name="..."` picks another name);
  - `defs.tool("read", defs.home("/lib/tools/base/read"))`: one tool by its path; it replaces a tool of the same name from the packs. The path can also be a library tool: `defs.tool("read", my.tool("read"))`;
  - `defs.drop("shell")`: drop one tool from the packs (also one that a base of `defs.load` gives);
  - the `.pack(...)` / `.tool(...)` of another library (see "Libraries" below).
  - `std.pack(...)` and the `.pack(...)` of a library also take `prefix="..."` (put before every tool name), `rename={"read": "cat"}` (the name of one tool, instead of prefix + its name) and `exclude=["grep"]` (leave tools out).
  - When two packs give the same name and the tools are not exactly the same, `--compile` stops with `SpecBad` instead of letting one hide the other. Use `prefix=`, `rename=`, `exclude=`, or pick one with `defs.tool(name, ...)`.
- `LLM`: a dict. `{}` = the llm kernel's default brain; `{"model": "luna"}` picks a brain pack of the kernel. Other keys must be in `llm_keys` (`temperature`, `max_tokens`, ...).
- `FSM`: `std.fsm()` borrows the four cells of the `agent-fsm` template (`idle`, `think`, `wait`, `act`; the cell programs stay in `$AOS_HOME/templates/agent-fsm/`). Your own machine:

  ```python
  def cell(name):
      return ["python3", defs.home("/templates/agent-fsm/%s.py" % name)]

  FSM = defs.fsm("idle", [
      defs.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
      defs.state("think", cell("brain"), {0: "wait", 10: "idle"}),
      defs.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
      defs.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
  ])
  ```

  `next` maps an exit code (0-255, or `"*"` for any other) to the next state; every state needs `0` or `"*"`.
- Optional, passed as `defs.main(..., meta=META, interfaces=INTERFACES, hooks=HOOKS, files=FILES)`:
  - `META`: more keys for `_metainfo.json`, like `{"cost": {"time_ms": 60000}, "resource": ["llm"]}`;
  - `INTERFACES`: laid over the default `interfaces.json`, like `{"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}` (`None` removes a default key);
  - `HOOKS`: writes `hooks.json`, adds `"hooks": "hooks.json"` to `interfaces.json` and the `on_start` / `on_stop` lines (they fire `after_start` / `after_stop`) to `loop.json`. Write it as
    - a dict `{hook name: entry}`, the entries as in any `hooks.json` (`event`, `handler`, `condition`, `every_ms`, `config`, ...);
    - `std.hooks()`: the hooks of the `agent-fsm` template (`std.hooks("eca-claude")` / `("eca-pi")` for those); they are read from `$AOS_HOME/templates/<template>/hooks.json` and copied in, so recompiling follows a changed template;
    - a list of those, laid one over the other (a later entry with the same name wins, `None` drops one): `HOOKS = [std.hooks(), {"timer": None, "mine": {...}}]`; but two hook groups (`std.hooks(...)` of two templates, the `HOOKS` of `defs.load`) that give one name with different entries are `SpecBad` unless a dict of yours after them names it;
    - or `defs.extern("hooks.json")`.
  - `FILES`: other files written as they are, like `{"ladder.json": {...}}` (a dict or list is written as JSON, a string as it is). The name is one file in this folder; it cannot be a file that agent.py, the skeleton or the running agent writes.

## Without FSM (eca bodies: Claude Code, pi)

An eca definition has no state machine: its skeleton (`_entry`, `loop.json`, `cli.json`, `screen/`, `interfaces.json`) comes from its template. Copy the template first, put an `agent.py` in it, and leave `FSM` out:

```python
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, hooks=HOOKS)      # no FSM
```

Then `--compile` writes only the content files (`SYSTEM`, `TOOLS`, `LLM`, `HOOKS`, and `FILES`, `META`) under the names the folder's `interfaces.json` gives, and checks `LLM` against its `llm_keys` (eca: `model` only). The skeleton is not touched; `INTERFACES` cannot be used. A folder without `interfaces.json`, or one that declares no file for something you declare, gets one `DefBad` line and nothing is written.

Paths: write paths outside this folder as `defs.home("/...")` (under `$AOS_HOME`) or `defs.env("AOS_WS", "/...")`; they are written as `{"$env": ..., "$path": ...}` and work on any machine and after any copy. Do not write `../` paths: they break when the folder is copied somewhere else.

`agent.py` is ordinary Python: use loops and small functions to build the lists. It should not use the network or read files outside this folder, apart from what the libraries read (packs, tool folders, `std.hooks`).

## Build on another agent.py

An agent that is another one plus a few changes: load the other `agent.py` and write only the changes.

```python
base = defs.load("../reviewer")        # runs ../reviewer/agent.py; its defs.main(...) only hands over its fields

DESCRIPTION = "Review a change and refuse anything without a test."
SYSTEM = base.SYSTEM + "Refuse a change that has no test.\n"
TOOLS  = [base.TOOLS,                                     # all tools of the base, as one pack
          defs.drop("grep"),                              # one of them out
          std.tool("base/peek_now_time", name="now")]     # one more
LLM    = {**base.LLM, "model": "luna"}
HOOKS  = [base.HOOKS, {"timer": {**base.HOOKS["timer"], "every_ms": 60000}}]   # one field of one hook; on_error and the rest stay
FSM    = defs.fsm(base.FSM, [defs.state("think", ["python3", defs.home("/templates/agent-fsm/brain.py")])])   # next stays the base's
defs.main(DESCRIPTION, SYSTEM, TOOLS, LLM, FSM, hooks=HOOKS)
```

- **It happens only when you run `--compile`.** The files written are whole, like any other definition: no `extends`, no `$override`, nothing that names the base. The running agent does not know there was a base, and the base folder does not have to be there later.
- **A changed base is followed only when you recompile** here. `defs.load` runs the base's `agent.py`, not its JSON files, so this folder gets what the base's `agent.py` says now, even if the base itself was not recompiled.
- `defs.load(path)`: the folder of another `agent.py` (or the `.py` file itself). A relative path starts at the folder of this `agent.py` (in a Python prompt: the current folder); `defs.env("AOS_WS", "/agents/reviewer")` works too. It does not search anywhere. Loading the base writes nothing anywhere.
- The base gives nine fields: `DESCRIPTION`, `SYSTEM`, `TOOLS`, `LLM`, `FSM`, `META`, `INTERFACES`, `HOOKS`, `FILES`. A base without `HOOKS` gives an empty group (no `hooks.json` here either, unless you add hooks); a base without `FSM` (an eca body) gives `FSM = None`. A field the base writes by hand (`defs.extern(...)`) cannot be built on: using it is one `SpecBad` line; not using it is fine.
- **Tools.** `base.TOOLS` is one pack. `base.tools(prefix="r_", rename={...}, exclude=[...])` is the same pack with other names, as for `std.pack`. A tool you write yourself (`defs.tool`, `std.tool`) replaces the base's tool of that name; `defs.drop` takes one out. A tool is always replaced as a whole: there is no "change one field of a tool".
- **Two bases (a diamond).** `TOOLS = [d1.TOOLS, d2.TOOLS]`: a tool the same in both is one tool; a tool that differs, or that one of them took out (`defs.drop`) and the other kept, is `SpecBad`. Say which you mean with `defs.tool(name, ...)` or `defs.drop(name)`. A tool taken out does not come back unseen.
- **Hooks.** `base.HOOKS` and `std.hooks()` are hook groups; `base.HOOKS["timer"]` is a copy of that hook, so `{**base.HOOKS["timer"], "every_ms": 60000}` changes one field and keeps the rest. When two groups (two bases, or `std.hooks()` of two templates) both have a hook of one name and the entries differ, it is `SpecBad`; pick one by writing that hook yourself in a dict after them (`None` drops it). A dict you write still replaces a hook as a whole, as before.
- **State machine.** `defs.fsm(base.FSM, [defs.state(...)], drop=["act"])`: a state of the base's name changes only the fields you give (`argv`, `next`, `timeout_ms`; the rest stay), a new name adds a state (give `argv` and `next`), `drop` takes states out; the whole table is checked again.
- Relative paths inside the base (a tool `path` or `env_file`, a hook `handler`, a file of the base folder named in a state's `argv`) are rewritten from the base folder, so they still point at the base's files here. Write paths in the base as `defs.home(...)` / `defs.env(...)` and nothing needs rewriting.
- While the base runs, its folder comes first on `sys.path`; afterwards `sys.path` and the modules it imported (other than `aos`) are put back, so `import helper` here gets this folder's `helper.py`. Two `agent.py` files that load each other is `SpecBad`.
- A wrong base (a missing folder, an error in its `agent.py`, a wrong declaration there) is one line, for example `strict: error: SpecBad defs.load('../reviewer'): ...`, and nothing is written.
- Do not `import` another `agent.py` instead: its `defs.main(...)` then only prints a warning and does nothing (it used to write the other folder with your arguments).
- In a Python prompt (`from aos.py.agent import defs`): `r = defs.load("/ws/agents/reviewer")`, then `defs.compile(...)` / `defs.write(...)` with `r.SYSTEM`, `[r.TOOLS, ...]` and so on. A folder written that way has no `agent.py` and cannot be recompiled; keep the lines in an `agent.py` if you want to.

## Linking tool packs: static or dynamic

How the tools of a pack get into `tools.json` is a compile option, like `gcc -static`:

```sh
python3 agent.py --compile             # the default, the same as --compile --static
python3 agent.py --compile --dynamic   # every pack that can be, linked dynamically
python3 agent.py --dry-run --dynamic   # look first
```

```python
TOOLS = [std.pack("look", link="dynamic"), std.pack("mailbox")]   # one pack its own way; link="static" too
```

- **Static (the default).** The tools of the pack are copied into `tools.json` one by one, with full paths. A tool added to the pack later shows up only after you recompile.
- **Dynamic.** `tools.json` names the pack file (`"$override": [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}]`) and aos reads it every time the agent starts. A tool added to the pack later shows up at the agent's next start, without recompiling.
- A `link=` on a pack wins over `--static` / `--dynamic`. Either way the pack is read when you compile, and the same checks run (a name two packs give with different tools is `SpecBad`).
- What only static linking can do:
  - **renamed tools.** A pack with `prefix=` or `rename=`, which includes every pack of a library other than `std` (its tools get `<name>_` by default), cannot be linked dynamically: at run time aos reads the pack as it is. Under `--dynamic` such a pack is linked statically and you get one `warning` line; `link="dynamic"` on it is `SpecBad`. `my.pack("look", prefix="", link="dynamic")` works (its tools keep their names).
  - **the `TOOLS` of `defs.load`.** They are the base's tools after its own changes, not a pack file, and the compiled files never name the base; under `--dynamic` they are linked statically, with a `warning` line.
- `exclude=` and `defs.drop(...)` on a dynamically linked pack write `"name": null` in `tools.json` (null = not a tool).
- Replacing one tool of a dynamically linked pack (`defs.tool("read", ...)`) works when your tool gives every field the pack's tool has: at run time aos lays your entry over the pack's field by field, so a field you leave out would stay. When that would happen, compiling is `SpecBad`: link that pack statically.
- What compiling cannot check: a tool added to a dynamically linked pack after you compiled. If it has the name of another tool of this agent, at run time the two are merged without a word, field by field, the later one winning (the packs in `$override` order, then the table). Recompile now and then, or link statically, if that matters.

## Libraries

A library is a folder of a fixed shape: `packs/<name>.json` (tool packs, like `$AOS_HOME/lib/packs`) and `tools/<folder>/` (tools). `std` comes with aos (`std = defs.std`); its root is `$AOS_HOME`, with its packs in `lib/packs`, its tools in `lib/tools` and its hooks and state machine cells in `templates/`. Declare another library with its root, an absolute path or a directive:

```python
my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))  # the name "my" is only for this agent.py
TOOLS = [std.pack("look"), my.pack("look")]          # the brain sees read, ls, ... and my_read
```

- The tools of another library get the library name and `_` in front (`my_read`); the tools of `std` keep their short names (`read`). The brain allows only letters, digits, `_` and `-` in a tool name.
- `tools.json` holds only full paths (`{"$env": "AOS_WS", "$path": "/lib/my/tools/read"}`), never the library name. A path written relative in a library's pack (`"../tools/read"`) is rewritten under the library root; it cannot leave the root.
- The root must be readable when `agent.py` runs: a variable that is not set, or a root that is not a folder, is `SpecBad`. Running `agent.py` therefore needs `AOS_HOME`, and for a root under `$AOS_WS`, `AOS_WS` too.
- In this first step a library has packs and tools only; hooks and state machines come from `std`.

## When a declaration is wrong

`--compile` and `--dry-run` check everything first and write nothing when something is wrong. You get one line, for example:

```
my_agent: error: SpecBad state think: next state 'wiat' is not one of the states (idle, think, wait, act) (fix the declaration in agent.py)
```

Then check the folder as usual: `agent_def` with `{"op": "check", "path": "my_agent"}` should answer `{"problems": []}`.
