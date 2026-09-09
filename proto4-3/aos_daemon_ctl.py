#!/usr/bin/env python3
"""aos-daemon-ctl 的命令列：對一個正在跑的 aos-daemon 下指令。

    aos-daemon-ctl add TARGET [aos-run 旗標…]
    aos-daemon-ctl rm DIR [--force]
    aos-daemon-ctl restart TARGET [旗標…]
    aos-daemon-ctl get DIR
    aos-daemon-ctl ls
    aos-daemon-ctl pause DIR
    aos-daemon-ctl resume DIR
    aos-daemon-ctl stop                  [--home H]

家怎麼決定：`--home H` → 環境變數 `AOS_DAEMON_HOME` → 預設 `~/.aos-daemon`，跟
`aos-daemon` 一樣。

`ls`／`get` 直接讀 `state.json`（daemon 每 0.5 秒寫一次），不丟請求、不用等 daemon
回；daemon 沒在跑時照樣讀最後一份 state.json，但 stderr 會提醒一句。

其他動作寫一個請求檔到 `H/requests/`，等 `H/requests/done/` 出現同名檔（上限 10 秒），
印 `ok`／`result`；`ok:false` 時退出碼 1。daemon 沒在跑時這些動作不丟檔，直接印
「daemon 沒在跑」、退出碼 1。`stop` 額外等 daemon 進程真的死掉（上限 10 秒）才回。

旗標原樣傳給 aos-run，所以這裡**不用 argparse**（不然 `--max-runs` 之類會被吃掉）：
只把 `--home H` 從任何位置挑出來，其他通通當成 aos-run 的事。
"""
import json
import os
import sys
import time

from aos_home import Home, alive, put_request, resolve_home

CMDS = ("ls", "get", "add", "rm", "restart", "pause", "resume", "stop")
ASK_TIMEOUT = 10.0      # 等 done/ 出現
STOP_TIMEOUT = 10.0     # 等 daemon 進程真的死掉


def _require_alive(home):
    """其他動作（非 ls／get）daemon 沒在跑就不丟檔，直接說清楚。"""
    if home.alive():
        return True
    print("daemon 沒在跑", file=sys.stderr)
    return False


def stop(home):
    """丟 `{"op":"stop"}`，等 `daemon.pid` 的 pid 死掉才回，上限 10 秒。"""
    if not _require_alive(home):
        return False
    pid = home.pid()
    put_request(home, {"op": "stop"})
    if _gone(pid, STOP_TIMEOUT):
        print("收工了（pid %d）" % pid)
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
    """讀 state.json 印表。`only` 是 `get DIR`（先 realpath 再查）。daemon 沒在跑時
    照樣印最後一份 state.json，但 stderr 提醒一句「這是最後的狀態」。
    """
    st = home.state()
    if st is None:
        print("沒有 state.json（daemon 沒起來過）", file=sys.stderr)
        return 1
    if not home.alive():
        print("daemon 沒在跑，這是最後的狀態", file=sys.stderr)
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
    if not _require_alive(home):
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
    home_dir = resolve_home(_pop_home(argv))
    if not argv or argv[0] not in CMDS:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    home = Home(home_dir)

    if cmd == "ls":
        return show(home)
    if cmd == "stop":
        return 0 if stop(home) else 1
    if not rest:
        print("%s 要給 %s" % (cmd, "TARGET" if cmd in ("add", "restart") else "DIR"),
              file=sys.stderr)
        return 2
    if cmd == "get":
        return show(home, rest[0])
    if cmd in ("add", "restart"):
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
