# aos_agent/__init__.py - 保留頂層說明、命令派發與主入口。
import os
import signal
import sys

import aos_flags
import aos_ws
import daemon_ctl as dc

PROG = "aos-agent"
HELP = """aos-agent - talk to and manage one agent hosted on an aos-daemon

usage: aos-agent [--daemon D] [--target NAME] SUBCOMMAND [FLAGS...] [ARGS...]
       aos-agent SUBCOMMAND --help        that subcommand's own help

subcommands:
  ctl      attach, list and manage agents (ctl --help lists its actions)
  say      put one message in its queue; prints the letter name
  listen   print its answer (wait for it, or show the last N)
  chat     one line per message, waits for each answer; Ctrl-C exits
  open     attach to its screen (--detach: open only)
  close    close its screen
  watch    follow its screen until one answer ends
  tools    its toolbox: ls, get, add, rm, reset
  llm      its brain settings: ls, set, rm, reset
  history  its conversation: ls, rm, summarize, set
  hook     its hooks: ls, get, add, rm, reset

flags:
  -d, --daemon D       the daemon's stack folder (default: $AOS_DAEMON, else ./.stack)
  -t, --target NAME    which agent, for every subcommand that takes one (same as after it)
  -h, --help           show this help

flag order: a flag belongs to the level it is listed under (aos-agent, the subcommand,
  the action) and may go anywhere after that level's name, also after later names and
  arguments: aos-agent ctl stop ann -d D = aos-agent -d D ctl stop ann. After -- nothing
  is read as a flag.
target: every subcommand except ctl add / rm / ls / who acts on -t, --target NAME
  (default: $AOS_AGENT); neither = TargetMissing. ctl start / stop / sleep / wake /
  pause / resume / where also take NAME as the last argument. Two different names =
  ArgumentsBad; ctl add / rm / ls / who take no -t (ArgumentsBad or FlagUnknown).
output: results on stdout only (one line per item, TAB-separated; --json where listed);
  reminders on stderr as "aos-agent: warning: ...".
exit codes: 0 ok; 1 error ("aos-agent: error: CODE reason" on stderr); 130 on Ctrl-C.
more: proto8/cmd/aos-agent/README.md (rules, codes, examples)"""

# bin 入口把自己的資料夾放在最前；有跟著帶的模組就用那份。
if os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                               "bin", "agent_files.py")):
    from agent_files import declared_files
else:
    from agent.agent_files import declared_files

from . import common, ctl, say, listen, chat, screen, tools, llm, history, hook
from .common import Fail, parse

SUBS = {"ctl": ctl.cmd,
        "say": say.cmd, "listen": listen.cmd, "chat": chat.cmd,
        "open": screen.cmd("open"), "close": screen.cmd("close"), "watch": screen.cmd("watch"),
        "tools": tools.cmd, "llm": llm.cmd, "history": history.cmd, "hook": hook.cmd}


def on_signal(sig, frame):
    """TERM／HUP 退 128＋訊號；共用回信箱由下一個讀者收逾時回信。"""
    raise SystemExit(128 + sig)


def main():
    for s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, on_signal)
    aos_flags.HELP = HELP                        # --help（旗標的位置，子命令後也認）：英文說明到 stdout、退 0
    a = sys.argv[1:]
    try:
        opts, rest = parse(a, {"--daemon": "daemon", "--target": "target"}, help=HELP, short=("-d", "-t"), sub="root")
        common.TOP = opts                            # 11-10 Q1：-d／-t 寫在後面也算，下層解到時寫回這份；用的時候才讀
        common.TOP_TARGET = opts.get("target")       # 坑-68（11-10）：子命令前的 -t 傳給子命令（common.target 合併、兩邊不同＝ArgumentsBad）
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s; see aos-agent --help)" % ", ".join(SUBS))
        if rest[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s; see aos-agent --help)" % (rest[0], ", ".join(SUBS)))
        SUBS[rest[0]](rest[1:])
    except dc.Already as e:          # 11-10 cli-sweep Q4＝A：已在那個狀態＝印一句、退 0
        print(e, flush=True)
    except Fail as e:
        aos_flags.die(PROG, e.code, e)
    except aos_ws.Error as e:
        aos_flags.die(PROG, e.code, e)
    except KeyboardInterrupt:
        sys.exit(130)
