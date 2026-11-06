# aos_agent/__init__.py - 保留頂層說明、命令派發與主入口。
import signal
import sys

import aos_flags
import aos_ws

PROG = "aos-agent"
HELP = """aos-agent - one interface for an agent hosted on aos-daemon (eca, loop / fsm agents alike); each subcommand acts on one agent.

  Attach and manage (ctl):
    aos-agent [--daemon D] ctl add [--name N] [--ws WS] [--stack S] [--limits JSON] XXX   attach one (XXX must declare aos-agent in
                                                       interfaces.json); waits until it is on the table, prints its stack (daemon refuses = AddRejected)
    aos-agent [--daemon D] ctl rm NAME                 detach it and delete its stack (closes its screen first; ignores AOS_AGENT; a stack that
                                                       covers the workspace / definition / daemon / cwd / home / another listed stack is kept)
    aos-agent [--daemon D] ctl ls [--json]             list every proc on the daemon table, one line
                                                       "NAME TAB STATE TAB WORKSPACE TAB QUEUED TAB REASON" (none = -)
    aos-agent [--daemon D] ctl state|status [--target NAME]            a few lines about this one
    aos-agent [--daemon D] ctl where [--stack|--ws] [--target NAME]    print its stack (default, = --stack) or its workspace (--ws)
    aos-agent [--daemon D] ctl who [--stack S] [--json]   which listed agent S (default $AOS_STACK) belongs to: the one whose stack is S
                                                       or above S; prints its name (--json: {"name", "stack", "ws", "def"})
    aos-agent [--daemon D] ctl start|stop|sleep|wake|pause|resume [--target NAME]
  Talk to it, its screen and settings:
    aos-agent [--daemon D] say [--target NAME] [WORDS...|-]  put one message in its queue; stdout prints the letter name
                                                       (no words or - = all of stdin is one message, one trailing newline dropped;
                                                       stdin is a terminal = ArgumentsBad)
    aos-agent [--daemon D] listen [--target NAME] [--timeout-s SECS] | [--last N] [--follow]
                                                       stdout carries only the answer text (notes go to stderr), so > file and pipes work;
                                                       --last / --follow print blocks: a line "== #N", the question lines prefixed "> ", the answer
    aos-agent [--daemon D] chat [--target NAME]        one line per message, waits for the answer; Ctrl-C exits (130), end of stdin exits 0
    aos-agent [--daemon D] open [--detach]|close|watch [--target NAME]   its screen (only if the definition declares the screen
                                                       sub-interface; the entry is run with ACTION [--detach])
    aos-agent [--daemon D] tools [--target NAME] [ls [--json]|get NAME|add [--override] [--no-cache] NAME PATH|rm NAME|reset]
                                                       its toolbox (the definition's registry with this agent's overlay on top)
    aos-agent [--daemon D] llm [--target NAME] [show|set KEY=VALUE...|reset]
                                                       its brain settings (the definition's with the keys this agent changed on top)

Target: --target NAME > $AOS_AGENT (ctl add, rm, ls ignore it); neither = TargetMissing. Names are looked up on the daemon table
  (read directly through daemon_ctl); not there = InstanceMissing. Which daemon: --daemon D > $AOS_DAEMON (that daemon's $AOS_STACK) > ./.stack in cwd;
  none = DaemonMissing. There is no --stack to pick the target (where's --stack / --ws only choose what to print; who's --stack is the path
  to look up, not a target). Printed paths are absolute. who: no row whose stack is S or above it = InstanceMissing; no S = StackMissing.
  A proc that failed to start or ended with an error (exit non-zero) stays on the table as stopped with a reason, which ls and state print;
  only one that exited 0 leaves the table.
sleep / wake: sleep = sleep now (the daemon SIGTERMs it, row sleeping, stack kept, it wakes by itself when the daemon starts);
  stop = stop after this round, needs start. start only starts stopped, wake only wakes sleeping; crossing them (start / stop on sleeping,
  wake / sleep on stopped) = daemon_ctl's PhaseBad passed on; asking for the state it is already in prints "already ..." and exits 0.
AOS_KERNEL: if set, ctl letters go there first (through daemon_ctl) for the judge. start / stop / sleep / wake / rm of that kernel itself
  (AOS_KERNEL is inside its stack) go straight to the daemon (a sleeping kernel never reads its own wake); after sending, a kernel that
  is not running = WaitFailed at once (the letter waits in its mailbox until it is back).
Replies: ctl add / rm / start / stop / sleep / wake share $AOS_STACK/daemon_reply/ (without AOS_STACK,
  <daemon>/<ctl mailbox>/reply/), matching their own in_reply_to. Unclaimed replies older than 600 seconds are collected by the next reader.
  applied: false = AddRejected (add) / CtlRejected (others), with the reply's code and msg. A result on the table may complete the wait
  after one extra second for its reply. No reply within 30 seconds = DaemonMissing; a reply without the requested result = WaitFailed.
Interface: touches only the daemon table and the agent's stack (queue/, history.jsonl, ctl / state windows); in the definition folder (the def
  column of its row) it reads only the interfaces.json declaration. screen = a folder program in the definition that declares aos-agent/screen,
  run as aos-exec --ws <ws> --stack <stack> <definition>/<entry> ACTION...; tools = a registry file, this agent's overlay is <stack>/tools.json
  (differences only: {"add": {NAME: entry}, "rm": [NAME]}; the body reads definition + overlay; reset deletes it);
  llm = a brain settings file (e.g. "llm.json"), the keys this agent changed live at the same relative path in its stack (reset deletes it).
  entry (optional): the body's entry in the definition (e.g. "body.json"); declared = add attaches <definition>/<entry> (def column is still
  the definition folder); not declared = attaches the definition folder itself.
  limits (optional): the resources this agent should get, {"mem_mb", "cpu_s", "procs", "file_mb", "files": positive integers; "user": a
  string} (the aos-sandbox keys); ctl add --limits JSON replaces the declared one as a whole ('{}' = no limits). An unknown key or a bad
  value = InterfaceBad (declared) / ArgumentsBad (--limits). They are included in the letter built by daemon_ctl.add_letter; the daemon applies them
  in the child process (setrlimit / switching user). ctl state prints a limits line when the daemon table row has one.
stdout carries results only; reminders go to stderr as warning lines `aos-agent: warning: SENTENCE` (chat's "> " prompt is on stderr too).
  Errors: one stderr line `aos-agent: error: CODE reason`, exit 1 (Ctrl-C exits 130, SIGTERM 143, SIGHUP 129; leaving listen --follow with
  Ctrl-C exits 0). In chat, an error about one message prints its error line and returns to the prompt; end of stdin then exits 1.
  No subcommand = ArgumentsBad. --help prints this text.
  Codes: ArgumentsBad, FlagUnknown, CommandUnknown, CommandMissing, DaemonMissing, InstanceMissing, InstanceExists, PathMissing, SessionBad,
  SendFailed, PostFailed, QuestionUnknown, AnswerMissing, WaitFailed, AddRejected, CtlRejected, TargetMissing, WsMissing, StackMissing,
  InterfaceMissing, InterfaceBad, PhaseBad, ScreenMissing, ScreenBad, ToolsMissing, LlmMissing, LlmBad. Errors from daemon_ctl use this program name (ProcMissing -> InstanceMissing); errors of the screen entry, aos-tools and aos-json pass through as they are.
Needs aos-post and aos-exec on PATH (tools also needs aos-tools in proto8/cmd/aos-tools/bin; llm set also needs aos-json)."""

from . import common, ctl, say, listen, chat, screen, tools, llm
from .common import Fail, parse

SUBS = {"ctl": ctl.cmd,
        "say": say.cmd, "listen": listen.cmd, "chat": chat.cmd,
        "open": screen.cmd("open"), "close": screen.cmd("close"), "watch": screen.cmd("watch"),
        "tools": tools.cmd, "llm": llm.cmd}


def on_signal(sig, frame):
    """TERM／HUP 退 128＋訊號；共用回信箱由下一個讀者收逾時回信。"""
    raise SystemExit(128 + sig)


def main():
    for s in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(s, on_signal)
    aos_flags.HELP = HELP                        # --help（旗標的位置，子命令後也認）：英文說明到 stdout、退 0
    a = sys.argv[1:]
    try:
        opts, rest = parse(a, {"--daemon": "daemon"})
        common.DAEMON = opts.get("daemon")
        if not rest:
            raise Fail("ArgumentsBad", "missing subcommand (%s; see aos-agent --help)" % ", ".join(SUBS))
        if rest[0] not in SUBS:
            raise Fail("CommandUnknown", "unknown subcommand %s (%s; see aos-agent --help)" % (rest[0], ", ".join(SUBS)))
        SUBS[rest[0]](rest[1:])
    except Fail as e:
        aos_flags.die(PROG, e.code, e)
    except aos_ws.Error as e:
        aos_flags.die(PROG, e.code, e)
    except KeyboardInterrupt:
        sys.exit(130)
