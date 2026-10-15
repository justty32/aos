#!/usr/bin/env python3
"""proto8 daemon 的 demo：起 daemon → 一條條丟控制指令、印回覆 → SIGTERM 收掉 → 印子程式寫出來的檔。

    python3 proto8/demo/run.py
    python3 proto8/demo/run.py fsm     （改跑 fsm 的 demo，見 fsm/run.py）

產物（控制資料夾、stdout、exit 檔）都放在 mktemp 建的暫存資料夾，跑完整個刪掉。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON = os.path.join(HERE, "..", "lib", "aos_daemon.py")
ONCE, TICK = os.path.join(HERE, "once", "loop.json"), os.path.join(HERE, "tick", "loop.json")
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg))


def short(x):
    """印的時候把 demo 資料夾的絕對路徑省掉。"""
    return json.dumps(x, ensure_ascii=False).replace(HERE + "/", "")


def send(ctl, n, cmd):
    """寫一條指令 NN-op.json，等 NN-op.json.done 出現，印回覆、刪掉 .done。"""
    name = "%02d-%s.json" % (n, cmd.get("op", "x") if isinstance(cmd, dict) else "x")
    tmp = os.path.join(ctl, "." + name)          # 先寫 . 開頭的檔再改名，daemon 不會讀到寫一半的
    with open(tmp, "w") as f:
        f.write(cmd if isinstance(cmd, str) else json.dumps(cmd))
    os.replace(tmp, os.path.join(ctl, name))
    done = os.path.join(ctl, name + ".done")
    while not os.path.exists(done):
        time.sleep(0.05)
    with open(done) as f:
        reply = json.load(f)
    os.remove(done)
    say("→ %s  %s" % (name, short(reply["request"])))
    if reply["ok"]:
        result = reply["result"]
        for r in result if isinstance(result, list) else [result]:
            say("     ok   %s" % short(r))
    else:
        say("     錯   %s: %s" % (reply["error"]["code"], reply["error"]["msg"].replace(HERE + "/", "")))


def lines(out, name):
    try:
        with open(os.path.join(out, name)) as f:
            return f.read().split()
    except OSError:
        return []


def main():
    tmp = tempfile.mkdtemp(prefix="aos-demo-")
    ctl, out = os.path.join(tmp, "ctl"), os.path.join(tmp, "out")
    os.makedirs(ctl)
    os.makedirs(out)
    # daemon.json、inst.json 用 {"$env": ...} 讀這幾個變數（daemon 自己的 ctl／state 窗必填）；id 要寫絕對路徑
    env = dict(os.environ, DEMO_CTL=ctl, DEMO_OUT=out, PYTHONDONTWRITEBYTECODE="1",
               DEMO_DAEMON_CTL=os.path.join(tmp, "daemon.ctl.json"), DEMO_DAEMON_STATE=os.path.join(tmp, "daemon.state.json"))
    say("暫存資料夾 %s（ctl/ 放指令、out/ 放子程式的輸出）" % tmp)
    # daemon 沒 inst：stdout 只在收工時吐一份總結，直接印出來
    daemon = subprocess.Popen([sys.executable, DAEMON, "daemon.json"], cwd=HERE, env=env)
    say("daemon 起來了，pid %d" % daemon.pid)
    n = iter(range(1, 100))
    try:
        say("== add：once 跑一次；tick 跑 5 次、每次隔 1 秒（次數、間隔寫在 tick/loop.json）")
        send(ctl, next(n), {"op": "add", "id": ONCE})
        send(ctl, next(n), {"op": "add", "id": TICK})
        time.sleep(1.5)
        say("== list：once 已經 done，tick 跑了幾次")
        send(ctl, next(n), {"op": "list"})
        send(ctl, next(n), {"op": "state", "id": TICK})
        say("== pause tick，等 2.5 秒，tick.out 不該再長")
        send(ctl, next(n), {"op": "pause", "id": TICK})
        before = len(lines(out, "tick.out"))
        time.sleep(2.5)
        say("   tick.out：暫停時 %d 行，2.5 秒後 %d 行" % (before, len(lines(out, "tick.out"))))
        send(ctl, next(n), {"op": "state", "id": TICK})
        say("== add_times +2，resume，再等 2.5 秒")
        send(ctl, next(n), {"op": "add_times", "id": TICK, "delta": 2})
        send(ctl, next(n), {"op": "resume", "id": TICK})
        time.sleep(2.5)
        send(ctl, next(n), {"op": "get", "id": TICK})
        say("== remove tick（等它這次跑完、行程結束才回），之後再問它就找不到")
        send(ctl, next(n), {"op": "remove", "id": TICK})
        time.sleep(0.3)
        send(ctl, next(n), {"op": "state", "id": TICK})
        say("== 錯的指令")
        send(ctl, next(n), {"op": "jump", "id": ONCE})
        send(ctl, next(n), "{這不是 JSON")
        say("== SIGTERM")
        daemon.send_signal(signal.SIGTERM)
        say("daemon 結束，退出碼 %d" % daemon.wait(10))
        for name in ("once.out", "once.exit", "tick.out", "tick.exit"):
            say("out/%-9s %s" % (name, " ".join(lines(out, name))))
    finally:
        if daemon.poll() is None:
            daemon.kill()
            daemon.wait()
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    if sys.argv[1:] == ["fsm"]:
        import runpy
        runpy.run_path(os.path.join(HERE, "fsm", "run.py"), run_name="__main__")
    else:
        main()
