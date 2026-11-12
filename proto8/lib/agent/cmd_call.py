"""cmd_call - 給腦用的工具叫下層指令的共用版：在工作區跑一支指令、stderr 原樣往上、退出碼不對＝它最後一行錯誤行的代號與原因當自己的錯；被 TERM／Ctrl-C 先收掉正在跑的那一群。

不是工具（沒有 _entry）；self_*、do_task、goal、mailbox_call（mailbox_*、clock_register）叫 call，agents_cmd、fork 借 kill_group。錯誤行一律走 tool_io.die（名字是 tool_io.start 記的那支）。
錯：下層最後一行錯誤行的代號與原因接上（C-52 例外 ⑤），沒那行＝CommandFailed；每次叫下層最多 TIMEOUT_S 秒，到時整群 KILL、算 CommandFailed（lib 契約規則 5）。
來由：thinking 2026-11/12/codebase-cleanup C1——原本九支 _entry 與 mailbox_call.py 各抄一份。訊號什麼時候裝、裝哪幾個由各支自己叫 catch_signals 決定（各支原本的時機不同）。
"""
import os
import re
import signal
import subprocess
import sys

import process_group
import tool_io

TIMEOUT_S = 60
ERR_RE = re.compile(r"aos-[a-z-]+: error: ([A-Z][A-Za-z]+) (.*)\Z")
child = None


def kill_group(p):
    """先 TERM 整群、等 5 秒，還在再 KILL、再等 5 秒；送訊號出任何 OSError 就不再等（agents_cmd、fork 用；做法在 lib/process_group.py）。"""
    process_group.stop(p, 5, 5, OSError)


def on_term(signum, frame):
    """正在跑的那一群還活著就 TERM 它（不等），自己退 128＋訊號號。"""
    if child is not None and child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except OSError:
            pass
    sys.exit(128 + signum)


def catch_signals(sigs=(signal.SIGTERM, signal.SIGINT)):
    """這幾個訊號交給 on_term（Ctrl-C 也收的＝退 130、不吐 traceback，R12）。"""
    for sig in sigs:
        signal.signal(sig, on_term)


def call(prog, args, ok=(0,), text=None, shown=3, fix=None):
    """prog args…（cwd＝$AOS_WS；text＝給它的 stdin，沒給＝/dev/null）：stderr 原樣往上；退出碼不在 ok＝它最後一行錯誤行當自己的錯
    （fix(代號, 原因) 回改過的原因；沒那行＝CommandFailed）。錯誤句裡只列 args 的前 shown 個。回 (退出碼, stdout, stderr)。"""
    global child
    args = list(args)
    try:
        child = subprocess.Popen([prog] + args, stdin=subprocess.DEVNULL if text is None else subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                                 cwd=tool_io.workspace())
    except OSError as e:
        tool_io.die("LaunchFailed", "cannot run %s (put it on PATH with proto8/install.sh): %s" % (prog, e))
    try:
        out, err = child.communicate(text, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        tool_io.die("CommandFailed", "%s %s took over %d s and was killed" % (prog, " ".join(args[:shown]), TIMEOUT_S))
    if err:                                     # 下層的 stderr 原樣透出（R10）
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
        sys.stderr.flush()
    if child.returncode not in ok:              # 給腦用的工具把下層錯翻成自己的錯
        mine = [m for m in map(ERR_RE.match, err.splitlines()) if m]
        if mine:
            code, reason = mine[-1].group(1), mine[-1].group(2)
            tool_io.die(code, fix(code, reason) if fix else reason)
        tool_io.die("CommandFailed", "%s %s exited %d" % (prog, " ".join(args[:shown]), child.returncode))
    return child.returncode, out, err
