"""aos.py.daemon_ctl - aos-daemon-ctl 的薄殼：daemon_ctl.X(ARG, flag=v)＝aos-daemon-ctl X --flag v ARG；daemon_ctl.attach(D) 回綁好 --daemon D 的把手。

    from aos.py import daemon_ctl
    daemon_ctl.ls(json=True)                       # $ aos-daemon-ctl ls --json        （daemon 不給＝指令自己的預設）
    daemon_ctl.shutdown(daemon=".stack")           # $ aos-daemon-ctl --daemon .stack shutdown
    d = daemon_ctl.attach(".stack"); d.ping()      # $ aos-daemon-ctl --daemon /abs/.stack ping
頂層名字照 aos-daemon-ctl 的子指令表（aos.apps.daemon_ctl.main.COMMANDS，不另抄）擋錯；一個呼叫＝一條指令。"""
import os

from aos.py import _shell

PROG = "aos-daemon-ctl"
POINTING = ("daemon",)


def subcommands():
    """aos-daemon-ctl 的子指令名。"""
    from aos.apps.daemon_ctl.main import COMMANDS
    return tuple(COMMANDS)


def attach(daemon):
    """綁好一台 daemon（轉成絕對路徑）的把手；不跑指令。"""
    if not daemon:
        raise _shell.Failed("daemon_ctl.attach", "give the daemon's stack folder", code="ArgumentsBad")
    return _shell.Proxy(PROG, ["--daemon", os.path.abspath(str(daemon))], top=subcommands)


def __getattr__(name):
    if not name.startswith("_") and _shell.word(name) in subcommands():
        return getattr(_shell.Proxy(PROG, pointing=POINTING), name)
    raise AttributeError("module aos.py.daemon_ctl has no %s (aos-daemon-ctl subcommands: %s; attach)" % (name, ", ".join(subcommands())))


def __dir__():
    return sorted(set(globals()) | set(subcommands()))
