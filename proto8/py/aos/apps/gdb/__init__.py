"""aos-gdb 指令本體：接上一隻 agent，開一個 Python REPL，裡面已經 import aos.gdb as g、a = g.attach(NAME)；庫本身在 py/aos/gdb。"""
import code
import os
import sys

from aos import flags as aos_flags

NAME = "aos-gdb"
HELP = """aos-gdb - open a Python REPL attached to one agent, to put stop triggers on it

usage: aos-gdb [--daemon D] NAME
       aos-gdb --help

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON)
  -h, --help       show this help

Opens Python with `import aos.gdb as g` and `a = g.attach(NAME, daemon=D)` done.
In it, for example:
  a.stop_before_tool("write")      stop when the tool is about to run (that step finishes first)
  a.stop_on_tool_error()           stop when any tool exits non-zero or times out
  a.stop_when("after_tool", sh="grep -q secret", times=2)
  a.say("hi"); a.wait_paused(); a.why(); a.where(); a.history(3)
  a.resume(); a.triggers(); a.remove("before_tool_1"); a.clear()
Every call prints the aos command behind it ($ ...); set g.echo = False to stop that.
The same library works in any python3 with $AOS_HOME/lib on sys.path.
More: proto8/py/aos/apps/gdb/README.md
exit codes: 0 left the REPL; 1 error (ArgumentsBad, TargetMissing, HooksMissing...); 130 Ctrl-C.
"""
BANNER = """aos-gdb: attached to %s (stack %s)
  g = aos.gdb, a = the agent.  Try: a.triggers(), a.stop_before_tool(), a.why(), help(a)
  Ctrl-D leaves; triggers stay on the agent until a.remove() / a.clear()."""


def main():
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--daemon": "daemon"}, help=HELP, short=("-d",), anywhere=True)
    except aos_flags.Error as e:
        aos_flags.die(NAME, e.code, "%s (usage: aos-gdb [--daemon D] NAME)" % e)
    if len(rest) != 1:
        aos_flags.die(NAME, "ArgumentsBad", "give one agent NAME (usage: aos-gdb [--daemon D] NAME)")
    import aos.gdb as g
    try:
        a = g.attach(rest[0], daemon=opts.get("daemon"))
    except g.Failed as e:
        aos_flags.die(NAME, "AttachFailed", str(e))
    try:
        import readline  # noqa: F401  （有就有上下鍵與歷史）
        import rlcompleter
        readline.parse_and_bind("tab: complete")
        readline.set_completer(rlcompleter.Completer({"g": g, "a": a}).complete)
    except ImportError:
        pass
    sys.ps1, sys.ps2 = "gdb> ", "...  "
    code.interact(banner=BANNER % (a.name, a.stack), local={"g": g, "a": a, "os": os}, exitmsg="")
