#!/usr/bin/env python3
"""proto8 通用 kernel 的 demo：aos-daemon 底下一個 aos-loop 拍通用 kernel（aos_kernel.py），判官是表上一格 inst。
三種被閘門包住的活同時搶：假腦（resource llm，睡 0.8 秒）、假 cpu 活（cpu，睡 0.6 秒）、問人（human，假人 1.5 秒後回信）。

    python3 proto8/demo/run.py kernel2                       （或直接 python3 proto8/demo/kernel2/run.py）
    python3 proto8/demo/kernel2/run.py judge-agent.json      （第 1 段改用 agent 判官，要先開 LM Studio；demo 預設不跑）

兩段：(1) 規則判官（judge-rules.json，假判官）：格數 llm 1、cpu 2、human 1，看 log 的起跑順序；
(2) 壞掉的判官（judge-broken.json，回的不是答案）：每次問都錯→這次退回確定規則，連錯 2 次（max_fails）就停在規則。
設定檔（daemon／loop／kernel）在暫存資料夾裡寫成完整檔；跑完收 daemon、確認沒漏行程、刪暫存資料夾。
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
LIB = os.path.abspath(os.path.join(HERE, "..", "..", "lib"))
GATE, DAEMON, KERNEL = (os.path.join(LIB, x) for x in ("aos_gate.py", "aos_daemon.py", "aos_kernel.py"))
ROOT = os.path.dirname(os.path.dirname(HERE))            # proto8/
PATH = os.pathsep.join([os.path.join(ROOT, "bin"), os.path.join(ROOT, "demo", "bin"), os.environ.get("PATH", "")])
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def start_daemon(tmp, judge, max_fails, human):
    """在 tmp 寫完整的 kernel／loop／daemon 設定（不靠指示詞），起 daemon。回 (Popen, 信箱, log, state)。"""
    mb, log, st = (os.path.join(tmp, x) for x in ("mb", "kernel.log.jsonl", "kernel.state.json"))
    k = write(os.path.join(tmp, "kernel.json"), {"mailbox": mb, "state": st, "log": log, "judge": os.path.join(HERE, judge),
                                                 "max_fails": max_fails, "slots": {"llm": 1, "cpu": 2, "human": 1}})
    lp = write(os.path.join(tmp, "loop.json"), {"inst": {"argv": [sys.executable, KERNEL, k], "cwd": HERE},
                                                "times": None, "interval_ms": 100})
    d = write(os.path.join(tmp, "daemon.json"), {"children": [lp], "interval_ms": 100, "ctl": os.path.join(tmp, "d.ctl.json"),
                                                 "state": os.path.join(tmp, "d.state.json")})
    env = dict(os.environ, PATH=PATH, PYTHONDONTWRITEBYTECODE="1", DEMO_HUMAN=human)   # 被包住的活在 kernel 的環境跑
    return subprocess.Popen([sys.executable, DAEMON, d], cwd=tmp, env=env, stdout=subprocess.DEVNULL), mb, log, st


def stop_daemon(p):
    p.send_signal(signal.SIGTERM)
    try:
        return p.wait(15)
    except subprocess.TimeoutExpired:
        p.kill()
        return p.wait()


def fake_human(d, stop, delay=1.5):
    """假人：看到 <pid>.q 就等 delay 秒寫 <pid>.a。"""
    done = set()
    while not stop.is_set():
        for n in sorted(os.listdir(d)):
            if n.endswith(".q") and n not in done:
                done.add(n)
                time.sleep(delay)
                with open(os.path.join(d, n[:-2] + ".a"), "w", encoding="utf-8") as f:
                    f.write("好，我回了（%s）" % n[:-2])
        time.sleep(0.05)


def call(mb, gate, who, priority=None):
    env = dict(os.environ, PATH=PATH, AOS_KERNEL=mb, PYTHONDONTWRITEBYTECODE="1")
    if priority:
        env["AOS_PRIORITY"] = priority
    p = subprocess.Popen([sys.executable, GATE, gate], cwd=HERE, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p.stdin.write(who)
    p.stdin.close()
    return p


def show_log(log, names, t0):
    with open(log, encoding="utf-8") as f:
        recs = [json.loads(x) for x in f]
    for r in recs:
        t = "+%4.1fs" % (r["t"] - t0)
        if r["event"] == "decide":
            run = "、".join(names.get(x, "?") for x in r["run"]) or "（沒有）"
            extra = "；判官錯：%s" % r["error"] if r.get("error") else ""
            print("         %s 決定（%-8s）跑 %s%s%s" % (t, r["how"], run, "，截掉 %d" % r["cut"] if r["cut"] else "", extra))
        elif r["event"] in ("start", "done"):
            print("         %s %-5s %-9s [%s]%s" % (t, "起跑" if r["event"] == "start" else "跑完", names.get(r["letter"], "?"),
                                          r["resource"], " %d ms" % r["ms"] if "ms" in r else ""))
        else:
            print("         %s 丟掉 %s：%s" % (t, names.get(r["letter"], "?"), r["error"]))


def scenario(tmp, judge, plan, max_fails=3):
    os.makedirs(tmp)
    human = os.path.join(tmp, "human")
    os.makedirs(human)
    stop = threading.Event()
    threading.Thread(target=fake_human, args=(human, stop), daemon=True).start()
    d, mb, log, st = start_daemon(tmp, judge, max_fails, human)
    names = {}
    try:
        t0 = time.time()
        procs = []
        for who, gate, pri in plan:
            p = call(mb, gate, who, pri)
            procs.append((who, p))
            names[p.pid] = who
            time.sleep(0.02)
        say("   丟的順序：%s" % "、".join(w for w, _, _ in plan))
        for who, p in procs:
            p.wait(60)
            p.stdout.close()
            p.stderr.close()
        names = {n: names.get(int(n.split(".")[1]), "?") for n in _letters(log)}
        show_log(log, names, t0)
        with open(st, encoding="utf-8") as f:
            s = json.load(f)
        say("   kernel state 窗：runs %d、served %d、judge_fails %d、judge_error %s" % (s["runs"], s["served"], s["judge_fails"], json.dumps(s["judge_error"], ensure_ascii=False)))
    finally:
        stop.set()
        say("   daemon 收工，退出碼 %d" % stop_daemon(d))


def _letters(log):
    with open(log, encoding="utf-8") as f:
        return {r["letter"] for r in map(json.loads, f) if "letter" in r}


def leftovers(root):
    out = []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open("/proc/%s/cmdline" % pid, "rb") as f:
                if root.encode() in f.read():
                    out.append(int(pid))
        except OSError:
            pass
    return out


def main():
    judge = sys.argv[1] if sys.argv[1:] and sys.argv[1].endswith(".json") else "judge-rules.json"
    tmp = tempfile.mkdtemp(prefix="aos-kernel2-demo-")
    say("暫存資料夾 %s；格數 llm 1、cpu 2、human 1；daemon 底下的 loop 每 100 ms 拍一次 kernel" % tmp)
    try:
        say("== 1. 判官 %s：兩封問人、三封假腦（low／high／沒寫）、三封 cpu 同時丟" % judge)
        scenario(os.path.join(tmp, "s1"), judge, [
            ("L-low", "gate-llm.json", "low"), ("C1", "gate-cpu.json", None), ("H1", "gate-human.json", None),
            ("L-normal", "gate-llm.json", None), ("C2", "gate-cpu.json", None), ("L-high", "gate-llm.json", "high"),
            ("H2", "gate-human.json", None), ("C3", "gate-cpu.json", None)])
        say("== 2. 壞掉的判官（judge-broken.json，max_fails 2）：每次問都錯 → 這次退回規則；連錯 2 次就不再問")
        scenario(os.path.join(tmp, "s2"), "judge-broken.json", [
            ("L-low", "gate-llm.json", "low"), ("L-high", "gate-llm.json", "high"), ("L-normal", "gate-llm.json", None),
            ("C1", "gate-cpu.json", None), ("C2", "gate-cpu.json", None), ("C3", "gate-cpu.json", None)], max_fails=2)
    finally:
        time.sleep(0.3)
        left = leftovers(tmp)
        say("漏掉的行程：%s" % (left or "沒有"))
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
