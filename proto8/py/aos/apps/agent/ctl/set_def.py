# aos/apps/agent/ctl/set_def.py - 換掉表上一隻 agent 的定義：停、拔、用同一個 stack 掛回（工作區、limits、auto_restart 照舊），表馬上換。
import contextlib
import io
import os
from aos import daemon_ctl as dc
from aos.agentlib import cli_cell, cli_linger
from ..common import Fail, bad_args, call_dc, daemon_path, find, note, parse, row_named, table_ref, via_kernel
from ..decl import close_screen_if_any, read_decl
from ..common import IFACE
from .shared import ctl_wait, need_table, timeout_opt, wait_for
from . import add, phase
from . import kit as kit_mod


HELP = """aos-agent ctl set-def - give an agent another definition; its stack and workspace stay

usage: aos-agent [--daemon D] ctl set-def [--kit KIT] [--timeout-s S] NAME DEF

DEF is the new agent folder, checked like ctl add (a folder; declaring aos-agent in its
interfaces.json is optional, a declared "entry" must exist in it).
set-def closes NAME's screen (an answering screen = SessionBad, nothing changed), stops it
(after this round, like ctl stop), detaches it (like ctl rm: its stack stays) and attaches it
again under the same name with DEF. Everything else on its table row stays: stack (history,
queue, mailbox, its own copies), workspace, limits, auto_restart. The table shows DEF at
once and keeps it when the daemon restarts.

  running               starts again with DEF (a new pid; history and queue kept)
  stopped / stopping    stays stopped; the next ctl start uses DEF
  sleeping              stays asleep; ctl wake (or a daemon restart) uses DEF

For a moment NAME is not on the daemon table: a letter sent to it then is refused.
If the stop fails or times out nothing else is changed (only its screen is closed). If
attaching it again fails after it was detached, the error says how to attach it by hand,
straight to the daemon (-d), so a kernel that refused it is not asked again:
  aos-agent -d DAEMON ctl add -n NAME -s STACK -w WS [--auto-restart] OLD-DEF
Through AOS_KERNEL the attach letter waits for a slot at most --timeout-s seconds: a kernel
that queues it refuses it when that time is up (SlotMissing), so it is never applied later.

Its own tools file in the stack (made by aos-agent tools add / rm) still overrides the old
definition's; a warning says so: look with aos-agent tools ls, or aos-agent tools reset.
An agent attached with ctl add --envs cannot be changed this way (ArgumentsBad): ctl rm it,
then ctl add --envs ... --stack ITS-STACK DEF. An agent cannot run set-def on itself (the
stop waits for this very round; ArgumentsBad): run it from outside.

With --kit, the kit is written into NAME's stack after it is detached and before it is
attached again (all checks first, so a bad kit changes nothing). To swap one kit for
another, run set-def --kit again with the other kit: it replaces the own copies (put back
as they were if NAME cannot be attached again).

flags:
""" + kit_mod.HELP_FLAG + """
      --timeout-s S   seconds to wait for the daemon at each step (default 30)
  -h, --help          show this help

exit codes: 0 set; 1 error (InstanceMissing, PathMissing, InterfaceBad,
  ArgumentsBad, CtlRejected, AddRejected, SessionBad, WaitFailed, DaemonMissing,
  KitMissing, KitBad...).
"""

KEEP_STOPPED = {"stopped", "stopping"}                # 原本停著或正在停的：掛回後還是停著（stopping＝已經有人要它停，代定照停）


def cmd(argv):
    opts, rest = parse(argv, {"--timeout-s": "timeout_s", "--kit": "kit"}, help=HELP)
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
    if os.environ.get("AOS_STACK") and os.path.realpath(os.environ["AOS_STACK"]) == os.path.realpath(a.stack):
        raise bad_args(HELP, "set-def cannot be used by %s on itself (the stop waits for this very round); run it from outside" % a.name)
    kit_steps = kit_mod.plan(opts["kit"], xxx, a.stack, a.name) if opts.get("kit") is not None else None   # --kit：先全查，壞了什麼都還沒動
    written = row.get("as_written") if isinstance(row.get("as_written"), dict) else {}
    kept = {k for k in ("ws", "stack") if isinstance(written.get(k), str)}   # 當初打成絕對路徑的格照樣原樣存
    if os.path.isabs(rest[1]):
        kept |= {"exec", "def"}
    ws = written["ws"] if isinstance(written.get("ws"), dict) else (a.ws if row.get("ws") else None)   # 指示詞原樣送回去；其餘用表上拼回的絕對路徑
    stack = written["stack"] if isinstance(written.get("stack"), dict) else a.stack
    old_def = row.get("def")
    kernel = via_kernel()
    daemon = daemon_path()                            # 掛不回去時的手動指令帶 -d：走 kernel 照抄會再被同一站擋（verify-night-1118 1b、1c）
    # 先組好掛回那封信（路徑、limits 有錯＝什麼都還沒動）
    _, request = call_dc(dc.add_letter, entry_target, daemon=None if kernel else table_ref(),
                         **add.add_kwargs(a.name, ws, stack, def_dir, row.get("limits"), None,
                                          {"auto_restart": bool(row.get("auto_restart"))}, None, kept))
    was = a.phase
    if was == "sleeping":
        request["procs_slept"] = [a.name]             # daemon 一封信的套法：added → slept＝上表、不起（aos-daemon docs/03「add＋sleep 同時」）
    elif was in KEEP_STOPPED:
        request["procs_stopped"] = [a.name]           # added → stopped＝上表、不起
    close_screen_if_any(a)                            # ctl stop 不關畫面（C′ B 包），換定義要自己先關：正在答＝SessionBad，什麼都還沒動
    if was not in {"stopped", "sleeping"}:            # running／stopping／stuck：先停（等這一輪跑完）；逾時＝cmd_stop 的錯，什麼都沒拔
        with contextlib.redirect_stdout(io.StringIO()):
            phase.cmd_stop(["--timeout-s", str(secs), a.name], look=True)
    detach(a, secs, kernel)
    drop_close_orders(a)
    made = []
    try:
        if kit_steps is not None:                     # 拔掉之後、掛回之前寫進 stack：掛回來的第一格就用 kit
            made = kit_mod.write(kit_steps)
            note(kit_mod.said(kit_steps, opts["kit"], a.name, xxx))
        ctl_wait("set-def", request, lambda letter: row_named(a.name) or (None if kernel else add.rejected(letter)),
                 "the daemon has not put %s back on the table yet" % a.name, "AddRejected", secs=secs, replied=kernel)
        if kernel:
            wait_for(lambda: row_named(a.name), "the daemon has not put %s back on the table yet" % a.name, secs)
    except Fail as e:
        kit_mod.undo(made, e)                         # 掛不回去＝收回剛寫的 kit、蓋掉的寫回（逾時說不準：留著）
        raise Fail(e.code, "%s; %s was detached and is not on the table now; attach it again by hand: aos-agent -d %s ctl add -n %s -s %s -w %s%s %s"
                   % (e, a.name, daemon, a.name, a.stack, a.ws, " --auto-restart" if row.get("auto_restart") else "", old_def or "OLD-DEF")) from e
    if kit_steps is None:                             # 套了 kit＝stack 那份就是 kit 的，不是疊在舊定義上
        warn_own_tools(a, old_def, xxx)
    now = (row_named(a.name) or {}).get("def") or xxx
    tail = {"sleeping": "it stays asleep; ctl wake (or a daemon restart) runs it",
            "stopped": "it stays stopped; ctl start runs it",
            "stopping": "it stays stopped; ctl start runs it"}.get(was, "it runs it now")
    print("definition of %s is now %s; %s (stack %s kept)" % (a.name, now, tail, a.stack))


def detach(a, secs, kernel):
    """拔：寄 procs_removed、等那列不在；stack 留著（同 ctl rm 不帶 --purge）。畫面在 cmd 一開頭就關了。"""
    gone = lambda _: row_named(a.name) is None
    ctl_wait("set-def", {"procs_removed": [a.name]}, gone, "the daemon has not removed %s yet" % a.name, "CtlRejected",
             secs=secs, replied=kernel)
    if kernel:
        wait_for(lambda: gone(None), "the daemon has not removed %s yet" % a.name, secs)


def drop_close_orders(a):
    """eca 的 ctl stop（after_stop hook）在 stack 小格留的延後關畫面到期單（screen_close.json）：畫面 set-def 一開頭就關了，
    單子留著＝之後才到期、去關掛回來那隻的新畫面。拔掉之後、掛回之前收掉（cooldown-1118 發現；使用者 11-18 裁「清單只限 set-def」，
    所以 aos-eca-screen close 不清、ctl rm 與 aos-agent close 留著照舊）。沒有那個小格或那份單子＝不做事。"""
    for kind in cli_linger.KINDS:
        cell = cli_cell.Cell(os.path.join(a.stack, kind), make=False)
        if os.path.isdir(cell.path):
            cli_linger.drop(cell)


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
