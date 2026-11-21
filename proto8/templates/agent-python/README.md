Look things up in the workspace and answer by mail (agent-python skeleton: an agent definition written as one agent.py).

This folder is one working agent definition. **`agent.py` is its source; every other file here (except this README) is compiled from it**, the way a C compiler turns a `.c` file into a `.o` file. You change `agent.py`, run one command, and the JSON files are written for you; you do not `mkdir` or edit them one by one.

- **What compiling is.** `python3 agent.py --compile` runs `agent.py` and writes the definition files (`fsm.json`, `tools.json`, ...) into this folder. From then on aos runs those files, not `agent.py`: like a `.o` file, they no longer need their source.
- **Compiling again overwrites.** Recompiling writes every declared file again as a whole, without asking, so a change made directly in a compiled file is gone. Change `agent.py` and recompile instead.
- **Static and dynamic linking.** Some things are copied into the compiled files when you compile, like a library linked statically into a program: `std.hooks()`, everything taken from another `agent.py` with `defs.load`, and by default the tools of a pack (`std.pack`, a library's `.pack`). A change there shows up only after you recompile. Other things are only named in the compiled files and read when the agent runs, like a library linked dynamically (a `.so`): the tool programs themselves and their `_tooldef.json` (what the brain is told about them), the state machine cells of `std.fsm()`, and the packs you link dynamically (`--dynamic`, see "Linking tool packs" below). A change there shows up before the agent's next brain call, without recompiling or restarting. So static linking fixes only the list of tools (names and paths), not the tools: when `$AOS_HOME` (or a library) is upgraded, an agent you already compiled reads the new tool programs and descriptions, loses a tool that was taken out, and stops if a cell it runs was taken out.

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

Keep the lines above `# ---- your agent` as they are: they find the `aos` package (`$AOS_HOME/lib` first, then an `aos/` folder next to `agent.py`, so a file named `aos.py` next to it does not get in the way when `AOS_HOME` is set), then import `defs` with `from aos.py.agent import defs` (everything below is `defs.something`). Keep the last line `defs.main(agent)`: it hands the agent to the command line (`--compile`, `--dry-run`, `--help`).

`defs.Agent` is the definition you write here; the handle of a running agent (what `agent.attach("ann")` gives) is a different class, `aos.py.agent.Attached`. Do not name your variable `agent` and also `from aos.py import agent` in the same file: the variable hides the module.

## Read this before you run --compile

1. **It overwrites, as a whole, every file `agent.py` declares**, every time, without asking. If you run it in a folder that already has hand-written `tools.json`, `fsm.json`, `system.txt` and so on, those are replaced. Look first with `python3 agent.py --dry-run`, or commit first. A file you want to keep writing by hand: give it another name and link the field to it, like `system=defs.extern("system.hand.txt")` (see "extern" below).
2. **Changes made directly in the compiled files are gone when you recompile.** That includes changes made by `agent_def tools` / `llm` / `system` or by an editor. Like a C compiler and its `.o` files: after it writes them, the files are ordinary definition files that anyone may change, and nothing remembers what was written. To keep a change, put it in `agent.py`.
3. **Renaming or removing a state of `fsm` can stop a running agent** that is sitting in that state (its `stage.txt` names a state that is no longer in `fsm.json`; aos-fsm then fails with `StateUnknown`). Rename states only when no agent using this definition is running.

What it does not touch: `_metainfo.json` keeps every key `agent.py` does not set (for example one you added by hand); `README.md` is written only when it is missing (one line: the description); any other file in the folder is left alone, also files an older `agent.py` wrote but the current one no longer declares (delete those yourself). Nothing in the folder marks it as compiled: delete `agent.py` and it is a plain definition.

## Files

| file | what it is | made from |
|---|---|---|
| `agent.py` | the source of this definition | you |
| `_entry` | mounts the agent on a daemon (`aos-agent ctl add`) | always written |
| `body.json` | runs the loop: `aos-loop loop.json` | always written |
| `loop.json` | runs `fsm.json` every 300 ms (`loop=` changes it); names the ctl, state and state flux files; with `hooks`, fires `after_start` / `after_stop` | always written; `loop=` |
| `fsm.json` | the state machine | `fsm=` |
| `interfaces.json` | names the other files (`entry`, `tools`, `llm`, `llm_keys`, `history`, `system`, and `hooks` with `hooks`) | always written; `interfaces=` is laid over it |
| `tools.json` | the tools | `tools=` |
| `llm.json` | brain settings | `llm=` |
| `system.txt` | the system text | `system=` |
| `_metainfo.json` | `summary` and `meta` keys | the description, `meta=` |
| `README.md` | this file | written only when missing |
| `hooks.json` | the hooks (none in this skeleton: `hooks={}`) | `hooks=` |
| `fn/<name>.py` (not in this skeleton) | one program for each function tool or hook | `@fn.tool` / `@fn.hook` functions in `tools=` / `hooks=` |
| any other name (not in this skeleton) | as given | `files=` |

## What you write in agent.py

One `defs.Agent(...)`: the description first, every other field by name (all lower case):

```python
agent = defs.Agent(
    "Look things up in the workspace and answer by mail.",
    system="...",
    tools=[...],
    llm={},
    fsm=std.fsm(),
    hooks={},
)

defs.main(agent)
```

`defs.Agent(description, *, system, tools, llm, fsm=None, hooks=None, meta=None, interfaces=None, files=None, loop=None)` only takes the fields; a wrong field is found when you compile (one `SpecBad` line, for example `tools must be a list ...`).

- the description (first, without a name): one English sentence: what the agent does. It becomes `summary` in `_metainfo.json`.
- `system`: the system text as a string, or `defs.extern("../shared/system.txt")`: `system.txt` becomes a link to a file you write yourself (see "extern" below; use it sparingly).
- `tools`: a list of
  - `std.pack("look")`: the tools of a pack of `std`, the library that comes with aos (`$AOS_HOME/lib/packs/look.json`). The pack is read when `agent.py` runs and, linked statically (the default), its tools are written into `tools.json` one by one (no `$override`), so a tool added to the pack later shows up after you recompile (dynamic linking: see "Linking tool packs");
  - `std.tool("base/read")`: one tool of `std` (`$AOS_HOME/lib/tools/base/read`), named after its folder (`name="..."` picks another name);
  - `defs.tool("read", defs.home("/lib/tools/base/read"))`: one tool by its path; it replaces a tool of the same name from the packs. The path can also be a library tool: `defs.tool("read", my.tool("read"))`;
  - `defs.drop("shell")`: drop one tool from the packs (also one that a base of `defs.load` gives);
  - the `.pack(...)` / `.tool(...)` of another library (see "Libraries" below);
  - a Python function marked `@fn.tool`, written in this `agent.py` (see "Functions as tools and hooks" below).
  - `std.pack(...)` and the `.pack(...)` of a library also take `prefix="..."` (put before every tool name), `rename={"read": "cat"}` (the name of one tool, instead of prefix + its name) and `exclude=["grep"]` (leave tools out).
  - When two packs give the same name and the tools are not exactly the same, `--compile` stops with `SpecBad` instead of letting one hide the other. Use `prefix=`, `rename=`, `exclude=`, or pick one with `defs.tool(name, ...)`.
- `llm`: a dict. `{}` = the llm kernel's default brain; `{"model": "luna"}` picks a brain pack of the kernel. Other keys must be in `llm_keys` (`temperature`, `max_tokens`, ...).
- `fsm`: `std.fsm()` borrows the four cells of the `agent-fsm` template (`idle`, `think`, `wait`, `act`; the cell programs stay in `$AOS_HOME/templates/agent-fsm/`). Your own machine:

  ```python
  def cell(name):
      return ["python3", defs.home("/templates/agent-fsm/%s.py" % name)]

  cells = defs.fsm("idle", [
      defs.state("idle",  cell("idle"),  {0: "think", 10: "idle"}),
      defs.state("think", cell("brain"), {0: "wait", 10: "idle"}),
      defs.state("wait",  cell("wait"),  {0: "act", 10: "wait", 11: "think"}),
      defs.state("act",   cell("act"),   {0: "think", 10: "idle"}, timeout_ms=0),
  ])
  ```

  and then `fsm=cells` in `defs.Agent(...)`. `next` maps an exit code (0-255, or `"*"` for any other) to the next state; every state needs `0` or `"*"`.

  A state machine compiles on its own too: `cells.compile("machines/counter")` writes only `fsm.json` there (`name="fsm.json"` picks another file name), `cells.dry_run()` gives `{"fsm.json": {...}}`, and `defs.main(cells)` as the last line of a script gives it `--compile [folder]` and `--dry-run` (no `--static` / `--dynamic`).
- Optional fields, by name in `defs.Agent(...)`:
  - `meta`: more keys for `_metainfo.json`, like `{"cost": {"time_ms": 60000}, "resource": ["llm"]}`;
  - `interfaces`: laid over the default `interfaces.json`, like `{"aos-observed": {"file": "observed.jsonl"}, "aos-agent": {"history": None}}` (`None` removes a default key);
  - `hooks`: writes `hooks.json`, adds `"hooks": "hooks.json"` to `interfaces.json` and the `on_start` / `on_stop` lines (they fire `after_start` / `after_stop`) to `loop.json`. Write it as
    - a dict `{hook name: entry}`, the entries as in any `hooks.json` (`event`, `handler`, `condition`, `every_ms`, `config`, ...);
    - `std.hooks()`: the hooks of the `agent-fsm` template (`std.hooks("eca-claude")` / `("eca-pi")` for those); they are read from `$AOS_HOME/templates/<template>/hooks.json` and copied in, so recompiling follows a changed template;
    - a Python function marked `@fn.hook("event", ...)` (see "Functions as tools and hooks" below);
    - a list of those, laid one over the other (a later entry with the same name wins, `None` drops one): `hooks=[std.hooks(), {"timer": None, "mine": {...}}]`; but two hook groups (`std.hooks(...)` of two templates, the `hooks` of `defs.load`) that give one name with different entries are `SpecBad` unless a dict of yours after them names it;
    - or `defs.extern("../shared/hooks.json")`: `hooks.json` becomes a link (see "extern" below; the whole field, not an item of the list).

    The skeleton has `hooks={}`: no hooks, but `hooks.json` is declared, so an agent made from it takes breakpoints (`aos-gdb`, `a.bp.add...`) and `aos-agent hook add` without any change. Keep that line when you rewrite the part below `# ---- your agent`; without it, setting a breakpoint is `HooksMissing`. Want the `agent-fsm` template's hooks (a timer that looks at the mailbox, ...)? Write `hooks=std.hooks()`.
  - `files`: other files written as they are, like `{"ladder.json": {...}}` (a dict or list is written as JSON, a string as it is). The name is one file in this folder; it cannot be a file that agent.py, the skeleton or the running agent writes.
  - `loop`: `defs.loop(every_ms=1000)`: the pause between two ticks of the loop, in milliseconds (`interval_ms` in `loop.json`; without `loop`, 300). A whole number >= 0 (0 = no pause, as aos-loop reads it). It needs `fsm` (without `fsm`, `loop.json` is the one of the skeleton you copied). Only the pause can be declared; the other keys of `loop.json` are worked out by the compile.

## extern: a link to a file you write (do not overuse it)

```python
system=defs.extern("../shared/system.txt")   # system.txt in the definition becomes a link to that file
```

`defs.extern(PATH)` compiles a field (`system`, `tools`, `llm`, `hooks`, or `fsm`) as a symbolic link to `PATH` instead of writing a file. The link sits on the field's usual file name (`system.txt`, `tools.json`, ...; without `fsm`, the name the folder's `interfaces.json` gives), and `interfaces.json` names that file as always.

- The link holds the path exactly as you wrote it: a relative path is counted from the folder the definition is compiled into (`--compile other/folder`: from there), an absolute path stays absolute. `defs.env(...)` / `defs.home(...)` cannot go into a link.
- The target must be there when you compile, and be a file; otherwise `--compile` stops with `SpecBad` and writes nothing. Its content is not checked (it is yours).
- Compiling again only remakes the link; it never touches the target. Editing the target takes effect without recompiling (from the agent's next brain call). Drop the `extern` and the next compile writes a plain file in place of the link (the target is still not touched).
- `--dry-run` prints the field as `{"$symlink": "../shared/system.txt"}`; `--compile` prints `wrote .../system.txt -> ../shared/system.txt`.
- `fsm` can only link to a file in the same folder (`defs.extern("fsm.hand.json")`): aos-loop resolves the link and would run the states as if the target's folder were the definition (tried on 11-20: the cells then miss this folder's `llm.json` and `tools.json`). `system`, `tools`, `llm` and `hooks` can point anywhere; relative paths inside a linked `tools.json` / `hooks.json` (a tool's `path`, a hook's `handler`) are counted from this definition folder, where the link is, not from the target's folder.
- To keep a file of this folder by hand (compiling never touches it), link to it under another name: `system=defs.extern("system.hand.txt")`. `defs.extern("system.txt")` would be a link to itself: `SpecBad`.
- `tools` and `hooks`: `defs.extern(...)` stands for the whole field (`tools=defs.extern(...)`), not an item of the list.
- In `defs.load`: a base's field linked to a file outside the base's folder comes over as the same link (counted again from the folder this one is compiled into); one linked to a file inside the base's folder cannot be built on (using it is one `SpecBad` line), since this definition would then run on another definition's file.

**Do not overuse this.** A link makes the definition depend on a file outside it:

- copy or move the definition without the target and it breaks; the agent then runs with no system text, silently. `agent_def check` reports a broken link (one problem for each), nothing else does. `agent_def new` copies the link as it is (like `cp -r`): a copy at another depth gets a broken relative link.
- some commands write through the link and change the shared file for every definition that links to it (`agent_def llm` / `tools`, `aos-tools add --file`); others replace the link with a plain file (`agent_def system`).
- git on Windows may check a link out as a text file.

If all you want is the text of a file at compile time, read it in Python instead: `system=open("x.txt").read()`. Use `extern` only when one hand-written file must stay the single live copy.

## Functions as tools and hooks

A tool or a hook can be one Python function in this `agent.py`, written the way a tool is written in the `tool-python` skeleton (`from aos.py import fn`):

```python
from aos.py import fn
import re


@fn.tool
def add(a: float, b: float) -> float:
    """Add two numbers and return the sum. Example: {"a": 2, "b": 3} -> 5

    Args:
      a: the first number
      b: the second number
    """
    return a + b


@fn.hook("before_tool", condition="ws_write")
def no_secrets(event):
    """Stop a ws_write that mentions a secret."""
    if re.search("secret", str(event.get("arguments"))):
        return fn.block("the arguments mention a secret")


agent = defs.Agent("...", system="...", tools=[std.pack("ws-write"), add], llm={}, fsm=std.fsm(), hooks=[no_secrets])
```

- **Compiling pulls each function out** into its own program, `fn/<name>.py` in this folder (mode 755): the setup lines that find `aos`, the imports it uses, the function as you wrote it (decorator included) and `fn.main(...)`. `tools.json` gets `"add": {"path": "fn/add.py"}`, `hooks.json` gets `"no_secrets": {"event": "before_tool", "handler": "fn/no_secrets.py", "condition": "ws_write"}`. From then on the program does not need `agent.py`; you may change it by hand, and the next compile writes it again as a whole. A function you take out of `agent.py` leaves its old `fn/` file behind (compiling deletes nothing).
- **Nothing is registered by itself**: a function is used only where you list it (`tools=[..., add]`, `hooks=[..., no_secrets]`). The name is the function's name, or `name=`; `prefix=` / `rename=` of `.pack(...)` rename the file too (`fn/base_check.py`). Two things that end up with one file name are `SpecBad`.
- **Description and parameters** (tools): as in `tool-python` - the docstring up to `Args:`, a type on every parameter (`str`, `int`, `float`, `bool`, `list`, `dict`), a line `name: ...` under `Args:`; or written out, `@fn.tool(description="...", params=[fn.param(...)], errors=[...], meta={...})`. Both are taken; the written one wins, one parameter at a time.
- **Hooks**: `@fn.hook("event", condition=..., timeout_ms=..., on_error=..., async_=True, name="...")`; every key except `name` goes into the `hooks.json` entry as written (`async_` is the `async` key). The function gets the event as a dict and returns `None` (go on), a dict of keys to change, or `fn.block("why")` (stop it; only events that can be stopped, like `before_tool` and `before_queue`). A function hook and a dict entry of one name: the later one in the list wins, as with dicts.
- **What a function may use**: Python builtins, its own parameters and variables, `fn`, and modules imported at the top of `agent.py` (`import re`; the program gets one import line for each name it uses, so `import os, re` with only `re` used gives `import re`). Anything else is `SpecBad` when you compile: a constant, function or class of `agent.py` (move it into the function), `defs` or `std` (at run time use `fn.fail` / `fn.block`), a module that sits next to `agent.py` (`import helpers`: the program cannot find it), a name `agent.py` does not define. That goes for the decorator line and the default values too (`@fn.tool(params=PARAMS)` uses `PARAMS`). It must be a plain `def` at the top of the file with only the `fn` decorator on it.
- **Relative paths in the function start at `fn/`**, the folder of the program, like any tool aos runs (`open("data.txt")` reads `fn/data.txt`). For the workspace use `os.environ["AOS_WS"]`.
- **`fn` is read from `$AOS_HOME/lib`** when the program runs (the program looks for `aos` only there, and takes `fn/` itself off the module path, so a tool called `json` does not hide the `json` module). Upgrading aos changes the programs of an agent you already compiled, the same as the tools of a statically linked pack.
- `defs.load`: the base's functions come over with `base.tools` / `base.hooks`, and compiling here pulls them out again into this folder's `fn/`; nothing points back at the base. `defs.drop("add")` writes no `fn/add.py`. An eca body (no `fsm`) gets `fn/` and its entries the same way.
- **Each hook run starts a Python** (about 20 ms); keep busy events like `before_tool` light.

## Without a state machine (eca bodies: Claude Code, pi)

An eca definition has no state machine: its skeleton (`_entry`, `loop.json`, `cli.json`, `screen/`, `interfaces.json`) comes from its template. Copy the template first, put an `agent.py` in it, and leave `fsm` out:

```python
agent = defs.Agent("...", system="...", tools=[...], llm={}, hooks={})   # no fsm
defs.main(agent)
```

Then `--compile` writes only the content files (`system`, `tools`, `llm`, `hooks`, and `files`, `meta`) under the names the folder's `interfaces.json` gives, and checks `llm` against its `llm_keys` (eca: `model` only). The skeleton is not touched; `interfaces` cannot be used. A folder without `interfaces.json`, or one that declares no file for something you declare, gets one `DefBad` line and nothing is written.

Paths: write paths outside this folder as `defs.home("/...")` (under `$AOS_HOME`) or `defs.env("AOS_WS", "/...")`; they are written as `{"$env": ..., "$path": ...}` and work on any machine and after any copy. Do not write `../` paths: they break when the folder is copied somewhere else.

`agent.py` is ordinary Python: use loops and small functions to build the lists. It should not use the network or read files outside this folder, apart from what the libraries read (packs, tool folders, `std.hooks`).

## Build on another agent.py

An agent that is another one plus a few changes: load the other `agent.py` and write only the changes.

```python
base = defs.load("../reviewer")        # runs ../reviewer/agent.py and takes the agent it hands to defs.main

agent = defs.Agent(
    "Review a change and refuse anything without a test.",
    system=base.system + "Refuse a change that has no test.\n",
    tools=[base.tools,                                    # all tools of the base, as one pack
           defs.drop("grep"),                             # one of them out
           std.tool("base/peek_now_time", name="now")],   # one more
    llm={**base.llm, "model": "luna"},
    hooks=[base.hooks, {"timer": {**base.hooks["timer"], "every_ms": 60000}}],   # one field of one hook; on_error and the rest stay
    fsm=defs.fsm(base.fsm, [defs.state("think", ["python3", defs.home("/templates/agent-fsm/brain.py")])]),   # next stays the base's
)

defs.main(agent)
```

- **It happens only when you run `--compile`.** The files written are whole, like any other definition: no `extends`, no `$override`, nothing that names the base. The running agent does not know there was a base, and the base folder does not have to be there later.
- **A changed base is followed only when you recompile** here. `defs.load` runs the base's `agent.py`, not its JSON files, so this folder gets what the base's `agent.py` says now, even if the base itself was not recompiled.
- `defs.load(path)`: the folder of another `agent.py` (or the `.py` file itself). A relative path starts at the folder of this `agent.py` (in a Python prompt: the current folder); `defs.env("AOS_WS", "/agents/reviewer")` works too. It does not search anywhere. Loading the base writes nothing anywhere.
- `defs.load` gives the `defs.Agent` that the base's `agent.py` hands to `defs.main` (a new copy each time), with ten fields: `base.description`, `base.system`, `base.tools`, `base.llm`, `base.fsm`, `base.meta`, `base.interfaces`, `base.hooks`, `base.files`, `base.loop`. A base without `hooks` gives an empty group (no `hooks.json` here either, unless you add hooks); like every field, the base's `hooks` comes over only when you write it (`hooks=base.hooks`, even when it is the skeleton's empty `{}`): an `agent.py` here without `hooks` has no `hooks.json` and takes no breakpoints; a base without `fsm` (an eca body) gives `base.fsm` = `None`. A field the base links to a file inside its own folder (`defs.extern("system.hand.txt")`) cannot be built on: using it is one `SpecBad` line; not using it is fine. A field linked to a file outside the base's folder comes over as the same link (see "extern").
- **Tools.** `base.tools` is one pack. `base.pack(prefix="r_", rename={...}, exclude=[...])` is the same pack with other names, as for `std.pack`. A tool you write yourself (`defs.tool`, `std.tool`) replaces the base's tool of that name; `defs.drop` takes one out. A tool is always replaced as a whole: there is no "change one field of a tool".
- **Two bases (a diamond).** `tools=[d1.tools, d2.tools]`: a tool the same in both is one tool; a tool that differs, or that one of them took out (`defs.drop`) and the other kept, is `SpecBad`. Say which you mean with `defs.tool(name, ...)` or `defs.drop(name)`. A tool taken out does not come back unseen.
- **Hooks.** `base.hooks` and `std.hooks()` are hook groups; `base.hooks["timer"]` is a copy of that hook, so `{**base.hooks["timer"], "every_ms": 60000}` changes one field and keeps the rest. When two groups (two bases, or `std.hooks()` of two templates) both have a hook of one name and the entries differ, it is `SpecBad`; pick one by writing that hook yourself in a dict after them (`None` drops it). A dict you write still replaces a hook as a whole, as before.
- **State machine.** `defs.fsm(base.fsm, [defs.state(...)], drop=["act"])`: a state of the base's name changes only the fields you give (`argv`, `next`, `timeout_ms`; the rest stay), a new name adds a state (give `argv` and `next`), `drop` takes states out; the whole table is checked again.
- Relative paths inside the base (a tool `path` or `env_file`, a hook `handler`, a file of the base folder named in a state's `argv`) are rewritten from the base folder, so they still point at the base's files here. Write paths in the base as `defs.home(...)` / `defs.env(...)` and nothing needs rewriting.
- While the base runs, its folder comes first on `sys.path`; afterwards `sys.path` and the modules it imported (other than `aos`) are put back, so `import helper` here gets this folder's `helper.py`. Two `agent.py` files that load each other is `SpecBad`.
- A wrong base (a missing folder, an error in its `agent.py`, a wrong declaration there) is one line, for example `strict: error: SpecBad defs.load('../reviewer'): ...`, and nothing is written.
- Do not `import` another `agent.py` instead: its `defs.main(...)` then only prints a warning and does nothing.

## Compiling from Python (a prompt, or one build script for several folders)

A `defs.Agent` compiles itself; `defs.main` is only the command line around it:

- `agent.dry_run(folder=None, link="static")` gives `{file name: content}` and writes nothing;
- `agent.compile(folder, link="static")` writes into `folder` (always give it) and gives the list of what it wrote.

So a build script does not need `defs.main`: build the agents and call `.compile(folder)` on each, one script for several folders:

```python
for name in ["ann", "bob"]:
    defs.Agent("Answer letters for %s." % name, system="You are %s.\n" % name,
               tools=[std.pack("mailbox")], llm={}, fsm=std.fsm(), hooks={}).compile("agents/" + name)
```

In a Python prompt (`from aos.py.agent import defs`): `r = defs.load("/ws/agents/reviewer")`, then `defs.Agent("...", system=r.system, tools=[r.tools, ...], ...).compile("/ws/agents/x")`. A folder written that way has no `agent.py` and cannot be recompiled; keep the lines in an `agent.py` if you want to.

## Linking tool packs: static or dynamic

How the tools of a pack get into `tools.json` is a compile option, like `gcc -static`:

```sh
python3 agent.py --compile             # the default, the same as --compile --static
python3 agent.py --compile --dynamic   # every pack that can be, linked dynamically
python3 agent.py --dry-run --dynamic   # look first
```

```python
tools=[std.pack("look", link="dynamic"), std.pack("mailbox")],   # one pack its own way; link="static" too
```

- **Static (the default).** The tools of the pack are copied into `tools.json` one by one, with full paths. A tool added to the pack later shows up only after you recompile. Only the list is fixed: each path still points into `$AOS_HOME` (or the library), and the tool program and its `_tooldef.json` there are read when the agent runs, so an upgrade of `$AOS_HOME` changes them for this agent too.
- **Dynamic.** `tools.json` names the pack file (`"$override": [{"$env": "AOS_HOME", "$path": "/lib/packs/look.json"}]`) and aos reads it before every brain call. A tool added to the pack later shows up from the agent's next brain call, without recompiling or restarting.
- A function tool (`@fn.tool`) is not in a pack: it is always one entry of the `tools` table, pointing at its own `fn/<name>.py` in this folder, with `--static` and `--dynamic` alike. Its program is fixed here until you recompile, but the `fn` it imports is read from `$AOS_HOME/lib` when it runs.
- A `link=` on a pack wins over `--static` / `--dynamic`. Either way the pack is read when you compile, and the same checks run (a name two packs give with different tools is `SpecBad`).
- What only static linking can do:
  - **renamed tools.** A pack with `prefix=` or `rename=`, which includes every pack of a library other than `std` (its tools get `<name>_` by default), cannot be linked dynamically: at run time aos reads the pack as it is. Under `--dynamic` such a pack is linked statically and you get one `warning` line; `link="dynamic"` on it is `SpecBad`. `my.pack("look", prefix="", link="dynamic")` works (its tools keep their names).
  - **the `tools` of `defs.load`.** They are the base's tools after its own changes, not a pack file, and the compiled files never name the base; under `--dynamic` they are linked statically, with a `warning` line.
- `exclude=` and `defs.drop(...)` on a dynamically linked pack write `"name": null` in `tools.json` (null = not a tool).
- Replacing one tool of a dynamically linked pack (`defs.tool("read", ...)`) works when your tool gives every field the pack's tool has: at run time aos lays your entry over the pack's field by field, so a field you leave out would stay. When that would happen, compiling is `SpecBad`: link that pack statically.
- What compiling cannot check: a tool added to a dynamically linked pack after you compiled. If it has the name of another tool of this agent, at run time the two are merged without a word, field by field, the later one winning (the packs in `$override` order, then the table). Recompile now and then, or link statically, if that matters.

## Libraries

A library is a folder of a fixed shape: `packs/<name>.json` (tool packs, like `$AOS_HOME/lib/packs`) and `tools/<folder>/` (tools). `std` comes with aos (`std = defs.std`); its root is `$AOS_HOME`, with its packs in `lib/packs`, its tools in `lib/tools` and its hooks and state machine cells in `templates/`. Declare another library with its root, an absolute path or a directive:

```python
my = defs.lib("my", defs.env("AOS_WS", "/lib/my"))  # the name "my" is only for this agent.py
tools=[std.pack("look"), my.pack("look")],           # the brain sees read, ls, ... and my_read
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

Then check the folder as usual: `agent_def` with `{"op": "check", "path": "my_agent"}` should answer `{"problems": []}`. Only check looks at whether what the definition calls is there: tool paths, the programs its states, loop and hooks run, and the types of `llm` values (`--compile` does not check these); what it cannot check on this machine, like a variable that is not set, comes in `"warnings"`.
