"""aos-gdb 指令本體：接上一隻 agent，開一個 Python REPL，裡面已經 import aos.gdb as g、a = g.attach(NAME)；庫本身在 py/aos/gdb。"""
import code
import os
import sys

from aos import flags as aos_flags

NAME = "aos-gdb"
HELP = """aos-gdb - open a Python REPL attached to one agent, to stop it when a condition holds

usage: aos-gdb [--daemon D] NAME
       aos-gdb --help

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON)
  -h, --help       show this help

Opens Python with `import aos.gdb as g` and `a = g.attach(NAME, daemon=D)` done.
In it, a.xxx is aos-agent xxx (a.say, a.listen, a.ctl, a.state) plus reading the stack
(a.where, a.history, a.observed, a.file); every breakpoint thing is under a.bp:
  b = a.bp.add("before_tool", tool="write")   hold it before write runs; returns the id "before_tool_1"
  a.bp.add("after_tool", tool="write")        pause after the tool ran, before the brain sees the result
  a.bp.add("tool_error", times=2)             the same, when tools exit non-zero or time out twice in a row
  a.bp.add("after_tool", sh="grep -q secret || exit 10")
  a.bp.add("watch", py=lambda t: len(t.history(0)) > 20)   another proc looks every 0.5 s and pauses it
  a.say("hi"); a.bp.wait_stopped(); a.bp.why(); a.where(); a.history(3)
  a.bp.resume()            go on (a held tool call runs as it was); takes no arguments
  a.bp.skip()              let a held before_tool call go, but do not run that tool
  a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False, times=3, once=True); a.bp.rm(b); a.bp.clear()
  a.bp.stop()              pause it now, without a breakpoint (a.bp.resume() goes on)
Every call prints the aos command behind it ($ ...); set g.echo = False to stop that.
The same library works in any python3 with $AOS_HOME/lib on sys.path.
More: proto8/py/aos/apps/gdb/README.md
exit codes: 0 left the REPL; 1 error (ArgumentsBad, TargetMissing, HooksMissing...); 130 Ctrl-C.
"""
BANNER = """aos-gdb: attached to %s (stack %s)
  g = aos.gdb, a = the agent, a.bp = its breakpoints.  Try: a.bp, a.bp.add("before_tool"), a.bp.why(), help(a.bp)
  Ctrl-D leaves; breakpoints stay (triggers on the agent, watchers on the daemon) until a.bp.rm(id) / a.bp.clear()."""


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
