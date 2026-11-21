"""aos-gdb 指令本體：開一個 Python REPL，已放好入口 aos.py 的 agent、daemon_ctl、std、defs、hooks（載入的 hook 宣告，--hooks／--def-hooks），給了 NAME 再放 a = agent.attach(NAME)；echo 打開。庫本身在 py/aos/py（入口）與 py/aos/gdb（斷點、讀檔、宣告）。

--hooks／--def-hooks：使用者 11-21「4.要做，我覺得可以在gdb啓動時給他選項，跟他說可以參考這份宣告，然後再去做一些事情。」（線 top-1121-gdbdecl，
紀錄 thinking/2026-11/21/gdb-參考宣告-1121.md）；宣告只是參考：讀不到一行 warning、照開。"""
import code
import os
import sys

from aos import flags as aos_flags

NAME = "aos-gdb"
HELP = """aos-gdb - open a Python REPL with aos.py ready, attached to one agent, to stop it when a condition holds

usage: aos-gdb [--daemon D] [--hooks FILE]... [--def-hooks] [NAME]
       aos-gdb --help

flags:
  -d, --daemon D   the daemon's stack folder (default: $AOS_DAEMON, else what aos-agent uses);
                   given = AOS_DAEMON is set to it inside the REPL, so agent.* and daemon_ctl.* use it too
  --hooks FILE     a hook declaration file (hooks.json: {point id: {"input": schema, ...}}) to use as a reference;
                   give it again for more files
  --def-hooks      also load the files NAME's definition lists under "hooks" in its interfaces.json
  -h, --help       show this help

Hook declarations are only a reference: a file that cannot be read is one warning line, and without
any the REPL works as it always does. With them, in the REPL:
  hooks                                        the points, how a.bp.add stops on each, the subject, the fields
  hooks.load(FILE); hooks.load_def(a); hooks.clear(); hooks.fields("after_tool")
  a.bp.add.<point>(...)                        declared points gdb does not know become kinds too; the subject
                                               (first argument) follows the declared "condition" / "subject"
  a.bp.add warns (and adds anyway) when the point is not declared, or a py condition reads ev["x"] for a
  field x the declared input does not have
  a.bp.event()                                 the event of the breakpoint it stopped at, laid out as declared

Opens Python with these names ready (from aos.py import agent, daemon_ctl, std;
from aos.py.agent import defs), and with NAME also a = agent.attach(NAME, daemon=D):
  a.say("hi"); a.listen(timeout_s=20)         a.X.Y(ARG, flag=v) is aos-agent --target NAME X Y --flag v ARG
  a.ctl.state(json=True); a.tools.ls(); a.hook.ls()
  agent.ctl.ls(); daemon_ctl.ls()             commands that take no --target
  a.look.where(); a.look.history(3)           read the stack's files (also observed, request, queue, stderr, file)
every breakpoint thing is under a.bp:
  b = a.bp.add.before_tool("write")           hold it before write runs; returns the breakpoint:
                                               b.id == 1 (a number, never used again), b.kind == "before_tool", b.fired ...
  a.bp.add.after_tool("write")                pause after the tool ran, before the brain sees the result
  a.bp.add.tool_error(times=2)                the same, when tools exit non-zero or time out twice in a row
  a.bp.add.after_tool(sh="grep -q secret || exit 10")
  a.bp.add.watch(py=lambda t: len(t.history(0)) > 20)   another proc looks every 0.5 s and pauses it
  a.bp.add                                     lists every kind (tab completes them)
the three controls wait until it stops again and show where (wait=False: return at once with p;
p.is_done() says if it is done, p.wait() gives the same result, p.cancel() stops waiting and takes nothing back):
  a.say("hi"); a.bp.resume()
                           # stopped at breakpoint 1 (before_tool: write)
  a.bp.resume()            go on (a held tool call runs as it was) and wait for the next stop;
                           not stopped (just after a.say) = sends nothing, only waits
  a.bp.step()              go one step of its fsm (idle, think, wait or act) and stop again
  a.bp.pause()             stop it now, without a breakpoint (VS Code's Pause)
  It never stops: idle with nothing queued for a.bp.idle_s seconds = "did not stop: it is idle";
  a line on stderr every a.bp.report_s seconds; Ctrl-C = stop waiting, the agent goes on.
  a.bp.why(); a.bp.held(); a.bp.stopped(); a.bp.notes()   where and why it stopped
  a.bp.event()             the whole event the breakpoint stopped on (fields laid out as the hook declaration says)
  a.bp.ls(); a.bp.get(b); a.bp.set(b, enabled=False, times=3, once=True); a.bp.rm(b); a.bp.clear()
                           set returns the breakpoint too; on disk number 3 is gdb_0003 (gdbw_0003 for a watcher)
Every call prints the aos command behind it on stderr ($ ...); aos.py.echo = False stops that.
The same names work in any python3 with $AOS_HOME/lib on sys.path (there echo is off).
More: proto8/py/aos/apps/gdb/README.md
exit codes: 0 left the REPL; 1 error (ArgumentsBad, AttachFailed...); 130 Ctrl-C.
"""
USAGE = "usage: aos-gdb [--daemon D] [--hooks FILE]... [--def-hooks] [NAME]"
BANNER = """aos-gdb: %s
  ready: agent, daemon_ctl, std, defs, hooks%s.  Try: %s%s
  Ctrl-D leaves; breakpoints stay (triggers on the agent, watchers on the daemon) until a.bp.rm(b) / a.bp.clear()."""


def main():
    try:
        opts, rest = aos_flags.parse(sys.argv[1:], {"--daemon": "daemon"}, switches={"--def-hooks": "def_hooks"},
                                     multi={"--hooks": "hooks"}, help=HELP, short=("-d",), anywhere=True)
    except aos_flags.Error as e:
        aos_flags.die(NAME, e.code, "%s (%s)" % (e, USAGE))
    if len(rest) > 1:
        aos_flags.die(NAME, "ArgumentsBad", "give at most one agent NAME (%s)" % USAGE)
    if opts.get("daemon"):
        os.environ["AOS_DAEMON"] = os.path.abspath(opts["daemon"])
    import aos.py
    from aos.py import agent, daemon_ctl, std, sh, Failed, Timeout
    from aos.py.agent import defs
    from aos.gdb import decl
    hooks = decl.current
    hooks.load(*opts.get("hooks", []), where=NAME)          # 宣告只是參考：讀不到的一行 warning、照開
    here = {"agent": agent, "daemon_ctl": daemon_ctl, "std": std, "defs": defs, "hooks": hooks,
            "sh": sh, "Failed": Failed, "Timeout": Timeout, "os": os}
    if rest:
        a = agent.attach(rest[0], daemon=opts.get("daemon"))
        try:
            stack = a.stack                     # 確認接得上（一條 aos-agent ctl state --json who）
        except Failed as e:
            aos_flags.die(NAME, "AttachFailed", str(e))
        here["a"] = a
        head, more, tries = "attached to %s (stack %s)" % (a.name, stack), ", a = %s, a.bp = its breakpoints, a.look = its files" % a.name, \
            "a.bp.add.before_tool(\"x\"), a.say(\"hi\"), a.bp.resume(), a.bp.step(), a.look.history(3), help(a.bp)"
        if opts.get("def_hooks"):
            hooks.load_def(a, where=NAME)
    else:
        head, more, tries = "no agent attached (a = agent.attach(NAME) to get one)", "", "agent.ctl.ls(), a = agent.attach(\"NAME\")"
        if opts.get("def_hooks"):
            aos_flags.warn(NAME, "--def-hooks needs an agent NAME; nothing loaded (hooks.load_def(a) after attaching)")
    said = ("\n  hook declarations: %d point(s) from %d file(s), only for reference (type hooks to see them)" % (len(hooks.points), len(hooks.files))
            if hooks else "")
    aos.py.echo = True
    try:
        import readline  # noqa: F401  （有就有上下鍵與歷史）
        import rlcompleter
        readline.parse_and_bind("tab: complete")
        readline.set_completer(rlcompleter.Completer(here).complete)
    except ImportError:
        pass
    sys.ps1, sys.ps2 = "gdb> ", "...  "
    code.interact(banner=BANNER % (head, more, tries, said), local=here, exitmsg="")
