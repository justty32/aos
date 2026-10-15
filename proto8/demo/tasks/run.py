#!/usr/bin/env python3
"""tasks 的 demo：用 daemon 跑一棵 tasks 樹（檢查 → 重試 → 並行兩件事 → 收尾）。

    python3 proto8/demo/tasks/run.py

產物（控制資料夾、子程式的輸出、log）都放在 mktemp 建的暫存資料夾，跑完先收程序再整個刪掉。
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.realpath(os.path.join(HERE, "..", "..", "bin"))
DAEMON = os.path.realpath(os.path.join(HERE, "..", "..", "lib", "aos_daemon.py"))
TOPS = ("pipeline", "pipeline-fail", "pipeline-broken")
OK, FAIL, BROKEN = (os.path.join(HERE, x, "loop.json") for x in TOPS)
TASKS = ("aos_seq.py", "aos_par.py", "aos_if.py")
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def short(x):
    """印的時候把 demo 資料夾的絕對路徑省掉。"""
    return json.dumps(x, ensure_ascii=False).replace(HERE + "/", "")


def send(ctl, n, cmd, quiet=False):
    """寫一條指令 NN-op.json（先寫 . 開頭再改名），等 NN-op.json.done，印回覆、刪掉 .done，回 result（錯回 None）。"""
    name = "%02d-%s.json" % (n, cmd["op"])
    tmp = os.path.join(ctl, "." + name)
    with open(tmp, "w") as f:
        json.dump(cmd, f)
    os.replace(tmp, os.path.join(ctl, name))
    done = os.path.join(ctl, name + ".done")
    while not os.path.exists(done):
        time.sleep(0.05)
    with open(done) as f:
        reply = json.load(f)
    os.remove(done)
    if not quiet:
        say("→ %s  %s" % (name, short(reply["request"])))
    if not reply["ok"]:
        say("     錯   %s: %s" % (reply["error"]["code"], reply["error"]["msg"].replace(HERE + "/", "")))
        return None
    if not quiet:
        say("     ok   %s" % short(reply["result"]))
    return reply["result"]


def tasks_procs(work):
    """現在活著的 tasks 程式（環境變數 DEMO_WORK＝這次的暫存資料夾），回 [程式名, ...]。"""
    found = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                argv = f.read().split(b"\0")
            with open("/proc/%s/environ" % pid, "rb") as f:
                env = f.read().split(b"\0")
        except OSError:
            continue
        if b"DEMO_WORK=" + work.encode() not in env:
            continue
        for a in argv[:2]:
            name = os.path.basename(a.decode(errors="replace"))
            if name in TASKS:
                found.append(name[:-3].replace("_", "-"))
    return found


def watch(work, peak, stop):
    """旁邊一條執行緒每 50ms 數一次 tasks 程式，記下最多的那一刻。"""
    while not stop.is_set():
        now = tasks_procs(work)
        if len(now) > len(peak):
            peak[:] = now
        time.sleep(0.05)


def wait_done(ctl, n, id_, limit=8):
    """每 0.2 秒 get 一次（不印），直到 state 是 done，再 get 一次印出來。"""
    end = time.monotonic() + limit
    while time.monotonic() < end:
        r = send(ctl, next(n), {"op": "get", "id": id_}, quiet=True)
        if r and r["state"] == "done":
            break
        time.sleep(0.2)
    return send(ctl, next(n), {"op": "get", "id": id_})


def show(path, label):
    try:
        with open(path) as f:
            text = f.read().rstrip("\n")
    except OSError:
        text = None
    if text is None:
        say("   %-12s （沒有這個檔）" % label)
        return
    for i, line in enumerate(text.split("\n") if text else [""]):
        say("   %-12s %s" % (label if i == 0 else "", line))


def run_one(ctl, n, work, log, id_, title):
    say("== %s" % title)
    peak, stop = [], threading.Event()
    t = threading.Thread(target=watch, args=(work, peak, stop))
    t.start()
    try:
        send(ctl, next(n), {"op": "add", "id": id_})
        r = wait_done(ctl, n, id_)
    finally:
        stop.set()
        t.join()
    say("   last_code ＝ %s" % (r and r["last_code"]))
    say("   取樣看到最多 %d 支 tasks 程式同時活著：%s" % (len(peak), " → ".join(peak)))
    say("   log（各層 stderr 寫 /dev/stderr 一路接上來）：")
    show(log, "")
    for name in ("tries", "probe.out", "report.txt", "notify.txt", "summary.txt"):
        show(os.path.join(work, name), name)
    os.remove(log)


def main():
    tmp = tempfile.mkdtemp(prefix="aos-demo-")
    ctl, work, log = os.path.join(tmp, "ctl"), os.path.join(tmp, "work"), os.path.join(tmp, "log")
    run = os.path.join(tmp, "run")
    os.makedirs(ctl)
    os.makedirs(work)
    os.makedirs(run)
    # daemon 的 cwd＝run/，裡面放指回本資料夾的捷徑：tasks 的相對 TARGET 照樣找得到，repo 裡不留東西
    # （inst 不寫 exit：tasks 讀子 aos_inst 的 stdout 結果拿碼）
    for top in TOPS:
        os.symlink(os.path.join(HERE, top), os.path.join(run, top))
    # inst.json 用 {"$env": ...} 讀這三個；PATH 前面加 proto8/bin，argv 才能直接寫 "aos seq"
    env = dict(os.environ, DEMO_CTL=ctl, DEMO_WORK=work, DEMO_LOG=log, PYTHONDONTWRITEBYTECODE="1",
               PATH=BIN + os.pathsep + os.environ.get("PATH", ""),
               DEMO_DAEMON_CTL=os.path.join(tmp, "daemon.ctl.json"), DEMO_DAEMON_STATE=os.path.join(tmp, "daemon.state.json"))
    say("暫存資料夾 %s（ctl/ 放指令、work/ 放步驟間傳的檔、log 收 stderr）" % tmp)
    # daemon 沒 inst：stdout 只在收工時吐一份總結，直接印出來
    daemon = subprocess.Popen([sys.executable, DAEMON, os.path.join(HERE, "daemon.json")], cwd=run, env=env)
    say("daemon 起來了，pid %d（cwd＝run/，tasks 的相對 TARGET 從這裡算）" % daemon.pid)
    n = iter(range(1, 1000))
    try:
        run_one(ctl, n, work, log, OK,
                "pipeline：MAX_TRIES=4、READY_AT=3（第 3 次檢查才好）→ 應該成功")
        run_one(ctl, n, work, log, FAIL,
                "pipeline-fail：同一棵樹（argv 用 $ref 借 pipeline 的），MAX_TRIES=2 → 重試用完、收尾不跑")
        run_one(ctl, n, work, log, BROKEN,
                "pipeline-broken：忘了給 READY_AT → check 根本沒跑，看錯誤從哪裡冒出來")
        say("== list：三個實例都 done，留在表上")
        for r in send(ctl, next(n), {"op": "list"}, quiet=True):
            say("   %s  state=%s runs=%d last_code=%s" % (short(r["id"]), r["state"], r["runs"], r["last_code"]))
        say("== SIGTERM")
        daemon.send_signal(signal.SIGTERM)
        say("daemon 結束，退出碼 %d" % daemon.wait(10))
    finally:
        if daemon.poll() is None:
            daemon.kill()
            daemon.wait()
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
