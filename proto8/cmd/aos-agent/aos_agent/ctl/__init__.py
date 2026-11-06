# aos_agent/ctl/__init__.py - 顯式派發 agent 的掛上與管理命令。
from ..common import Fail, parse
from . import add, rm, phase, ls, state, where, who

SUBS = {"add": add.cmd, "rm": rm.cmd, "start": phase.cmd_start, "stop": phase.cmd_stop, "sleep": phase.cmd_sleep, "wake": phase.cmd_wake,
            "pause": phase.cmd_pause_resume("pause"), "resume": phase.cmd_pause_resume("resume"),
            "ls": ls.cmd, "state": state.cmd, "status": state.cmd, "where": where.cmd, "who": who.cmd}


def cmd(argv):
    """ctl＝掛上與管理（11-05 使用者「我希望掛上和管理這塊，能夠放到aos-agent ctl這個子命令下。」）。"""
    _, argv = parse(argv)                            # ctl 跟它的子命令之間也是旗標的位置（--help 認、別的 FlagUnknown）
    if not argv:
        raise Fail("ArgumentsBad", "ctl needs one of %s" % ", ".join(SUBS))
    if argv[0] not in SUBS:
        raise Fail("CommandUnknown", "ctl: unknown subcommand %s (%s)" % (argv[0], ", ".join(SUBS)))
    SUBS[argv[0]](argv[1:])
