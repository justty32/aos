#!/usr/bin/env python3
"""aos-daemon 的命令列：背景化、丟請求、等回音、讀 state.json 印表。

    aos-daemon start|stop|ls|get DIR|add TARGET [aos-run 旗標…]|rm DIR [--force]
               |update TARGET [旗標…]|pause DIR|resume DIR   [--home H]
    aos-daemon run [--home H]       前台跑（`start` 背景開的就是這個）

`ls`／`get` 直接讀 `state.json`（daemon 每 0.5 秒寫一次），不丟請求、不用等 daemon 回。
其他動作寫一個請求檔到 `H/requests/`，等 `H/requests/done/` 出現同名檔（上限 10 秒），
印 `ok`／`result`；`ok:false` 時退出碼 1。

旗標原樣傳給 aos-run，所以這裡**不用 argparse**（不然 `--max-runs` 之類會被吃掉）：
只把 `--home H` 從任何位置挑出來，其他通通當成 aos-run 的事。
"""
import json
import os
import signal
import subprocess
import sys
import time

from aos_daemon import Daemon
from aos_home import Home, alive, put_request

ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aos-daemon")
CMDS = ("run", "start", "stop", "ls", "get", "add", "rm", "update", "pause", "resume")
ASK_TIMEOUT = 10.0      # 等 done/ 出現
STOP_TIMEOUT = 3.0      # 等 daemon 自己退，超過就 SIGTERM

_spawned = []           # 留著 Popen 的參考，免得 GC 掉時噴 ResourceWarning


def start(home, timeout=10.0):
    """背景開一個 daemon，等到 `state.json` 裡的 pid 就是新開的那隻才說「起來了」。"""
    if home.alive():
        print("已經在跑（pid %d）" % home.pid())
        return False
    home.ensure()
    with open(home.logf, "a", encoding="utf-8") as log:
        p = subprocess.Popen([sys.executable, ENTRY, "run", "--home", home.dir],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             start_new_session=True, cwd=home.dir)
    _spawned.append(p)
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = home.state()
        if st and st.get("pid") == p.pid and alive(p.pid):
            print("起來了（pid %d，家在 %s）" % (p.pid, home.dir))
            return True
        if p.poll() is not None:
            break
        time.sleep(0.05)
    print("開了但等不到 state.json，看 %s" % home.logf, file=sys.stderr)
    return False


def stop(home):
    """丟 `{"op":"stop"}`，它會自己把所有 aos-run 收掉。3 秒不退就補一發 SIGTERM。"""
    pid = home.pid()
    if not home.alive():
        print("本來就沒在跑")
        return True
    put_request(home, {"op": "stop"})
    if _gone(pid, STOP_TIMEOUT):
        print("收工了（pid %d）" % pid)
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    if _gone(pid, STOP_TIMEOUT):
        print("收工了（SIGTERM，pid %d）" % pid)
        return True
    print("收不掉（pid %d）" % pid, file=sys.stderr)
    return False


def _gone(pid, secs):
    t0 = time.time()
    while time.time() - t0 < secs:
        if not alive(pid):
            return True
        time.sleep(0.05)
    return False


def show(home, only=None):
    """讀 state.json 印表。`only` 是 `get DIR`（先 realpath 再查）。"""
    st = home.state()
    if st is None:
        print("沒有 state.json（daemon 沒起來過）", file=sys.stderr)
        return 1
    runs = st.get("runs", {})
    if only is not None:
        key = os.path.realpath(only)
        if key not in runs:
            print("沒有在跑：%s" % key, file=sys.stderr)
            return 1
        runs = {key: runs[key]}
    print("DIR  PID  PAUSED  RUNS  LAST_EXIT")
    for k, e in sorted(runs.items()):
        print("%s  %s  %s  %s  %s" % (k, e.get("pid"), "yes" if e.get("paused") else "no",
                                      e.get("runs"), e.get("last_exit")))
    return 0


def ask(home, req):
    """丟請求、等 `done/` 同名檔冒出來，印 ok／result。`ok:false`＝退出碼 1。"""
    if not home.alive():
        print("daemon 沒在跑（先 aos-daemon start）", file=sys.stderr)
        return 1
    name = put_request(home, req)
    donef = os.path.join(home.done, name)
    t0 = time.time()
    while time.time() - t0 < ASK_TIMEOUT:
        if os.path.exists(donef):
            with open(donef, encoding="utf-8") as f:
                out = json.load(f)
            print("ok=%s result=%s" % (out.get("ok"),
                                       json.dumps(out.get("result"), ensure_ascii=False)))
            return 0 if out.get("ok") else 1
        time.sleep(0.05)
    print("等不到回應：%s" % donef, file=sys.stderr)
    return 1


def _pop_home(argv):
    """把 `--home H`／`--home=H` 從任何位置挑掉，其他旗標留給 aos-run。"""
    for i, a in enumerate(list(argv)):
        if a == "--home" and i + 1 < len(argv):
            argv.pop(i)                 # --home
            return argv.pop(i)          # H
        if a.startswith("--home="):
            argv.pop(i)
            return a.split("=", 1)[1]
    return None


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    home_dir = _pop_home(argv) or os.environ.get("AOS_HOME")
    if not argv or argv[0] not in CMDS:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if not home_dir:
        print("沒有家：給 --home 或設 AOS_HOME", file=sys.stderr)
        return 2
    home = Home(home_dir)

    if cmd == "run":
        Daemon(home).serve()
        return 0
    if cmd == "start":
        return 0 if start(home) else 1
    if cmd == "stop":
        return 0 if stop(home) else 1
    if cmd == "ls":
        return show(home)
    if not rest:
        print("%s 要給 %s" % (cmd, "TARGET" if cmd in ("add", "update") else "DIR"),
              file=sys.stderr)
        return 2
    if cmd == "get":
        return show(home, rest[0])
    if cmd in ("add", "update"):
        return ask(home, {"op": cmd, "target": os.path.abspath(rest[0]), "args": rest[1:]})
    if cmd == "rm":
        force = "--force" in rest
        d = [a for a in rest if a != "--force"]
        if not d:
            print("rm 要給 DIR", file=sys.stderr)
            return 2
        return ask(home, {"op": "remove", "dir": os.path.abspath(d[0]), "force": force})
    return ask(home, {"op": cmd, "dir": os.path.abspath(rest[0])})       # pause／resume


if __name__ == "__main__":
    sys.exit(main())
