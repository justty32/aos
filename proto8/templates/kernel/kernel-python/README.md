Pass every request on to the daemon, managing nothing yet (kernel-python skeleton: a kernel definition written as one kernel.py).

This folder is one working kernel definition. **`kernel.py` is its source; every other file here (except this README) is compiled from it**, the way a C compiler turns a `.c` file into a `.o` file, and the same way `agent.py` works for an agent (`templates/agent-python`). What the kernel does, its keys and its hook points are in [the kernel README](../README.md); this page is only about writing it as `kernel.py`.

## Make your own kernel from it

```sh
cp -r $AOS_HOME/templates/kernel/kernel-python perm
cd perm
# change the part of kernel.py under "# ---- your kernel", then:
python3 kernel.py --dry-run       # optional: compile and print what would be written, write nothing
python3 kernel.py --compile       # compile: write the definition files into this folder
aos-daemon-ctl add perm           # mount it, from the folder above (add -d DAEMON as usual)
```

Keep the lines above `# ---- your kernel` as they are: they find the `aos` package and import `defs` with `from aos.py.kernel import defs`. Keep the last line `defs.main(kernel)`: it hands the kernel to the command line (`--compile`, `--dry-run`, `--help`).

Compiling again overwrites, as a whole, every file `kernel.py` declares (`_entry`, `loop.json` or `daemon.json`, `kernel.json`, `loop_hooks.json`, `interfaces.json`, `fn/<name>.py`), without asking; a change made directly in one of them is gone. `README.md` is written only when it is missing; any other file (`.env`, an endpoint program of an llm kernel) is left alone. The station reads `kernel.json` again every round, so a recompile takes effect at the next round; a change of the body (`body=`) needs the row restarted.

## What you write in kernel.py

```python
from aos.py import fn                 # only if you write a hook as a function

@fn.hook("before_verdict")
def no_night_jobs(event):
    """Refuse procs named night-something."""
    names = (event.get("body") or {}).get("procs_added") or {}
    if any(str(n).startswith("night") for n in names):
        return fn.block("no night jobs here")

kernel = defs.Kernel(
    "Let at most two procs run at once, and no night jobs.",
    knobs={"max_running": 2, "queue": True},   # the rest of kernel.json, written as given
    hooks=[no_night_jobs],                     # a dict {name: entry}, @fn.hook functions, or a list of those
    program="kernel",                          # or "kernel_llm" (the llm kernel: adds interfaces.json with the ledger)
    body=defs.loop(every_ms=300),              # or defs.daemon(every_ms=300)
)
defs.main(kernel)
```

| field | what it does | left out |
|---|---|---|
| description (first) | one sentence; goes into `kernel.json` and the seed `README.md` | required |
| `knobs=` | the keys of `kernel.json` (`allowed`, `max_running`, `queue`, `next`... for `kernel`; `slots`, `endpoints`... for `kernel_llm`), written as given and not checked here: the program ignores keys it does not know | `{}`: manage nothing |
| `hooks=` | hooks of `before_verdict`, `after_verdict`, `before_reply` go into `kernel.json`; with `body=defs.loop(...)`, hooks of `after_start`, `after_stop`, `before_run`, `after_run` go into `loop_hooks.json`. A function is pulled out into `fn/<name>.py` (same rules as in `agent.py`: it may use builtins, `fn` and modules imported at the top) | no hooks |
| `program=` | `"kernel"` (the station that admits procs) or `"kernel_llm"` (the llm kernel) | `"kernel"` |
| `body=` | `defs.loop(every_ms=N)`: one row of a daemon (`_entry` runs `aos-loop loop.json`, like `procs-kernel`); `defs.daemon(every_ms=N)`: a daemon of its own with a sweeper row (`aos-daemon daemon.json`, like `daemon-kernel` and `llm-kernel`). Any other keyword goes into that file as it is, unchecked, and replaces a key of the same name the compile writes (`defs.daemon(procs={...})` = no sweeper row); `every_ms` and `interval_ms` together = `SpecBad` | like `templates/start-api`: `loop` for `kernel`, `daemon` for `kernel_llm` |

Without `defs.main` (a build script, the REPL): `kernel.dry_run()` gives the files, `kernel.compile("FOLDER")` writes them.

Not there yet: building on another `kernel.py` (`defs.load`), linking a field to a hand-written file (`defs.extern`), extra files (`files=`), and the endpoint programs of an llm kernel (keep `endpoints/` by hand next to the compiled files).
