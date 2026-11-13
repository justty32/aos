# aos_agent/ctl/__init__.py - 顯式派發 agent 的掛上與管理命令。
import aos_flags

from .. import common
from ..common import Fail, actions, parse
from . import add, rm, phase, ls, state, where, who, set_def

SUBS = {"add": add.cmd, "rm": rm.cmd, "set-def": set_def.cmd, "start": phase.cmd_start, "stop": phase.cmd_stop, "sleep": phase.cmd_sleep, "wake": phase.cmd_wake,
            "pause": phase.cmd_pause_resume("pause"), "resume": phase.cmd_pause_resume("resume"),
            "ls": ls.cmd, "state": state.cmd, "status": state.cmd, "where": where.cmd, "who": who.cmd}


NO_TARGET = ("add", "rm", "set-def", "ls", "who")               # 不看 --target／AOS_AGENT 的動作


HELPS = [add.HELP, rm.HELP, set_def.HELP, ls.HELP, state.HELP, where.HELP, who.HELP, *phase.HELP.values()]
HELP = """aos-agent ctl - attach, list and manage agents on the daemon table

usage: aos-agent [--daemon D] ctl ACTION [FLAGS...] [ARGS...]
       aos-agent ctl ACTION --help

stopping and starting again (three pairs; start / wake / resume only undo their own pair):
  what you want            command   how it stops                 table after  back with  daemon restart
  finish this round, stop  stop      writes its ctl, waits        stopped      start      stays stopped
  stop right now           sleep     SIGTERM (SIGKILL after 10 s) sleeping     wake       wakes it
  hold in place            pause     writes its ctl; still alive  running      resume     -
  take it off the table    rm        stop, then remove the row    (no row)     add again  -   (stack kept unless --purge)
  the whole daemon         aos-daemon-ctl shutdown (every proc sleeps; all wake when it restarts)

actions:
""" + actions(HELPS, "aos-agent [--daemon D] ctl ") + """

flags:
  -h, --help   show this help
  short names: -t --target, -j --json, -n --name, -w --ws, -s --stack, -y --yes

exit codes: 0 done; 1 error (PhaseBad, InstanceMissing, AddRejected...).
more: proto8/cmd/aos-agent/README.md
"""


def cmd(argv):
    """派發掛上與管理的二層動作。"""
    _, argv = parse(argv, help=HELP, sub=True)
    hint = "(%s; see aos-agent ctl --help)" % ", ".join(SUBS)
    if not argv:
        raise Fail("ArgumentsBad", "ctl needs one of %s (see aos-agent ctl --help)" % ", ".join(SUBS))
    if argv[0] not in SUBS:
        raise Fail("CommandUnknown", "ctl: unknown subcommand %s %s" % (argv[0], hint))
    if common.TOP_TARGET and argv[0] in NO_TARGET:      # 坑-68：這幾個不吃 --target，前面給了不默默丟掉
        raise Fail("ArgumentsBad", "ctl %s does not take --target (it was given before the subcommand; see aos-agent ctl %s --help)" % (argv[0], argv[0]))
    if argv[0] in NO_TARGET:
        aos_flags.hide("--target")                  # 寫在動作後的 -t 也不收（FlagUnknown），不默默寫回頂層
    SUBS[argv[0]](argv[1:])
