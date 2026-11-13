# aos_agent/ctl/set_def.py - 換掉表上一隻 agent 的定義：stack、工作區、limits、auto_restart 照舊，下一次起來才用新的。
# 已知缺口（aos-daemon）：同名 procs_added 換的設定只活在跑著的 daemon 裡，那隻還沒重起、daemon 自己先重啟＝表上回到舊定義（test_set_def 兩支 expectedFailure）。
import os
import daemon_ctl as dc
from ..common import Fail, bad_args, call_dc, daemon_path, find, note, parse, row_named
from ..decl import read_decl
from ..common import IFACE
from .shared import ctl_wait, need_table, timeout_opt
from . import add, phase


HELP = """aos-agent ctl set-def - give an agent another definition; its stack and workspace stay

usage: aos-agent [--daemon D] ctl set-def [--restart] [--timeout-s S] NAME DEF

DEF is the new agent folder (checked like ctl add: it must declare aos-agent in interfaces.json).
Everything else on NAME's table row stays: stack (history, queue, mailbox, its own copies),
workspace, limits, auto_restart. The daemon takes the new definition the next time NAME starts;
until then it keeps running the old one and its table row still shows the old one. A definition
set but not started yet is lost when the daemon itself restarts first (the row comes back with
the old one): start NAME, or use --restart, before the daemon goes down.

  stopped or sleeping   the next ctl start / wake uses DEF
  running               without --restart: a warning says it still runs the old one
                        --restart: closes its screen, stops it after this round, starts it with DEF

Its own tools file in the stack (made by aos-agent tools add / rm) still overrides the old
definition's; a warning says so: look with aos-agent tools ls, or aos-agent tools reset.
An agent attached with ctl add --envs cannot be changed this way (ArgumentsBad): ctl rm it,
then ctl add --envs ... --stack ITS-STACK DEF.

flags:
      --restart       stop and start it now so DEF takes effect (not for an agent changing itself)
      --timeout-s S   seconds to wait for the daemon at each step (default 30)
  -h, --help          show this help

exit codes: 0 set; 1 error (InstanceMissing, PathMissing, InterfaceMissing, InterfaceBad,
  ArgumentsBad, CtlRejected, SessionBad, DaemonMissing...).
"""


def cmd(argv):
    opts, rest = parse(argv, {"--timeout-s": "timeout_s"}, {"--restart": "restart"}, help=HELP)
    secs = timeout_opt(opts, HELP)
    if len(rest) != 2:
        raise bad_args(HELP, "set-def takes NAME and the new agent folder DEF")
    xxx, _, entry_target, def_dir = add.definition(rest[1], "set-def")
    need_table()
    a = find(rest[0])
    row = a.row
    if not isinstance(row.get("exec"), str):          # --envs 掛的：表上 exec 是一張單子，這裡組不回去
        raise bad_args(HELP, "%s was attached with --envs or extra arguments (its table row does not run a plain definition); "
                       "aos-agent ctl rm %s, then ctl add ... --stack %s %s" % (a.name, a.name, a.stack, rest[1]))
    if opts.get("restart") and os.environ.get("AOS_STACK") and os.path.realpath(os.environ["AOS_STACK"]) == os.path.realpath(a.stack):
        raise bad_args(HELP, "--restart cannot be used by %s on itself (the stop waits for this very round); leave it out, or run it from outside" % a.name)
    written = row.get("as_written") if isinstance(row.get("as_written"), dict) else {}
    kept = {k for k in ("ws", "stack") if isinstance(written.get(k), str)}   # 當初打成絕對路徑的格照樣原樣存
    if os.path.isabs(rest[1]):
        kept |= {"exec", "def"}
    ws = written["ws"] if isinstance(written.get("ws"), dict) else row.get("ws")          # 指示詞原樣送回去
    stack = written["stack"] if isinstance(written.get("stack"), dict) else a.stack
    old_def = row.get("def")
    _, request = call_dc(dc.add_letter, entry_target, name=a.name, ws=ws or None, stack=stack, def_dir=def_dir,
                         limits=row.get("limits"), auto_restart=bool(row.get("auto_restart")), daemon=daemon_path(), kept=kept)
    # 同名 procs_added＝daemon 把設定換成這份、在跑的不重起（N-54）；表上那列到下一次起來才換，所以只等回信、不看表
    ctl_wait("set-def", request, lambda _: True, "the daemon has not accepted the new definition of %s" % a.name, "CtlRejected",
             secs=secs, replied=True)
    warn_own_tools(a, old_def, xxx)
    if a.phase in {"stopped", "sleeping"}:
        print("definition of %s set to %s; its next %s uses it, unless the daemon restarts first (stack %s kept)"
              % (a.name, xxx, "ctl wake" if a.phase == "sleeping" else "ctl start", a.stack))
        return
    if not opts.get("restart"):
        note("%s still runs its old definition (%s); the new one takes effect on its next start and is lost if the daemon "
             "restarts first: aos-agent ctl set-def --restart %s %s, or ctl stop then ctl start" % (a.name, old_def, a.name, rest[1]))
        print("definition of %s set to %s for its next start (stack %s kept)" % (a.name, xxx, a.stack))
        return
    phase.cmd_stop(["--timeout-s", str(secs), a.name])
    phase.cmd_start(["--timeout-s", str(secs), a.name])
    now = (row_named(a.name) or {}).get("def")
    print("definition of %s is now %s (stack %s kept)" % (a.name, now or xxx, a.stack))


def warn_own_tools(a, old_def, new_def):
    """stack 裡這隻自己那份 tools（aos-agent tools add／rm 寫的）的 $override 指回舊定義的 tools 檔，換定義後還疊在舊的上面：提醒一行、不改寫。"""
    if not isinstance(old_def, str) or os.path.realpath(old_def) == os.path.realpath(new_def):
        return
    try:
        decl, _ = read_decl(old_def, IFACE)
    except Fail:
        return
    rel = (decl or {}).get("tools")
    if isinstance(rel, str) and rel and os.path.isfile(os.path.join(a.stack, rel)):
        note("%s has its own %s in its stack, which still overrides the old definition's (%s); "
             "check it with aos-agent tools --target %s ls, or drop it with aos-agent tools --target %s reset"
             % (a.name, rel, old_def, a.name, a.name))
