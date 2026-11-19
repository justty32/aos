"""aos-gdb 指令本體：開一個 Python REPL，已放好入口 aos.py 的 agent、daemon_ctl、std、defs，給了 NAME 再放 a = agent.attach(NAME)；echo 打開。庫本身在 py/aos/py（入口）與 py/aos/gdb（斷點、讀檔）。"""
import code
import os
import sys

from aos import flags as aos_flags

NAME = "aos-gdb"
HELP = """aos-gdb - open a Python REPL with aos.py ready, attached to one agent, to stop it when a condition holds

usage: aos-gdb [--daemon D] [NAME]
       aos-gdb --help

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON, else what aos-agent uses);
                   given = AOS_DAEMON is set to it inside the REPL, so agent.* and daemon_ctl.* use it too
  -h, --help       show this help

Opens Python with these names ready (from aos.py import agent, daemon_ctl, std;
from aos.py.agent import defs), and with NAME also a = agent.attach(NAME, daemon=D):
  a.say("hi"); a.listen(timeout_s=20)         a.X.Y(ARG, flag=v) is aos-agent --target NAME X Y --flag v ARG
  a.ctl.state(json=True); a.tools.ls(); a.hook.ls()
  agent.ctl.ls(); daemon_ctl.ls()             commands that take no --target
  a.look.where(); a.look.history(3)           read the stack's files (also observed, request, queue, stderr, file)
every breakpoint thing is under a.bp:
  b = a.bp.add.before_tool("write")           hold it before write runs; returns the id "before_tool_1"
  a.bp.add.after_tool("write")                pause after the tool ran, before the brain sees the result
  a.bp.add.tool_error(times=2)                the same, when tools exit non-zero or time out twice in a row
  a.bp.add.after_tool(sh="grep -q secret || exit 10")
  a.bp.add.watch(py=lambda t: len(t.history(0)) > 20)   another proc looks every 0.5 s and pauses it
  a.bp.add                                     lists every kind (tab completes them)
  a.say("hi"); a.bp.wait_stopped(); a.bp.why()
  a.bp.resume()            go on (a held tool call runs as it was); takes no arguments
  a.bp.skip()              let a held before_tool call go, but do not run that tool
  a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False, times=3, once=True); a.bp.rm(b); a.bp.clear()
  a.bp.stop()              pause it now, without a breakpoint (a.bp.resume() goes on)
Every call prints the aos command behind it on stderr ($ ...); aos.py.echo = False stops that.
The same names work in any python3 with $AOS_HOME/lib on sys.path (there echo is off).
More: proto8/py/aos/apps/gdb/README.md
exit codes: 0 left the REPL; 1 error (ArgumentsBad, AttachFailed...); 130 Ctrl-C.
"""
BANNER = """aos-gdb: %s
  ready: agent, daemon_ctl, std, defs%s.  Try: %s
  Ctrl-D leaves; breakpoints stay (triggers on the agent, watchers on the daemon) until a.bp.rm(id) / a.bp.clear()."""


def main():
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--daemon": "daemon"}, help=HELP, short=("-d",), anywhere=True)
    except aos_flags.Error as e:
        aos_flags.die(NAME, e.code, "%s (usage: aos-gdb [--daemon D] [NAME])" % e)
    if len(rest) > 1:
        aos_flags.die(NAME, "ArgumentsBad", "give at most one agent NAME (usage: aos-gdb [--daemon D] [NAME])")
    if opts.get("daemon"):
        os.environ["AOS_DAEMON"] = os.path.abspath(opts["daemon"])
    import aos.py
    from aos.py import agent, daemon_ctl, std, sh, Failed, Timeout
    from aos.py.agent import defs
    here = {"agent": agent, "daemon_ctl": daemon_ctl, "std": std, "defs": defs, "sh": sh, "Failed": Failed, "Timeout": Timeout, "os": os}
    if rest:
        a = agent.attach(rest[0], daemon=opts.get("daemon"))
        try:
            stack = a.stack                     # 確認接得上（一條 aos-agent ctl state --json who）
        except Failed as e:
            aos_flags.die(NAME, "AttachFailed", str(e))
        here["a"] = a
        head, more, tries = "attached to %s (stack %s)" % (a.name, stack), ", a = %s, a.bp = its breakpoints, a.look = its files" % a.name, \
            "a.bp, a.bp.add.before_tool(\"x\"), a.bp.why(), a.look.history(3), help(a.bp)"
    else:
        head, more, tries = "no agent attached (a = agent.attach(NAME) to get one)", "", "agent.ctl.ls(), a = agent.attach(\"NAME\")"
    aos.py.echo = True
    try:
        import readline  # noqa: F401  （有就有上下鍵與歷史）
        import rlcompleter
        readline.parse_and_bind("tab: complete")
        readline.set_completer(rlcompleter.Completer(here).complete)
    except ImportError:
        pass
    sys.ps1, sys.ps2 = "gdb> ", "...  "
    code.interact(banner=BANNER % (head, more, tries), local=here, exitmsg="")
