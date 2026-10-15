#!/usr/bin/env python3
"""proto8 LLM kernel 的 demo：aos-daemon 底下一個 aos-loop 每 100 ms 拍一次 kernel（aos_kernel_llm.py），
呼叫者都經閘門（aos_gate.py）叫同一顆假腦（睡 1 秒），看 kernel 照什麼順序服務。

    python3 proto8/demo/run.py kernels/llm    （或直接 python3 proto8/demo/kernels/llm/run.py）

三段：(1) 級數／deadline：先一封佔住唯一的格，再同時丟 low、normal、high、deadline 快到、deadline 已過；
(2) aging：一封 low 跟一串不斷進來的 normal（快腦）；(3) 報時員巢狀（boss 問 clerk、clerk 查 clock），
兩個 agent 的腦都包了閘門、一格就夠：boss＝定義資料夾 boss/（腦 brain.json＝經閘門叫假腦）；clerk 借 demo/fsm/clerk 的定義，
boss 的工具 tools/clerk.json 在 clerk 的 frame 放一份 boss 的 brain.json（綁定，蓋過 clerk 預設的腦）。kernel／loop／daemon 的設定在暫存資料夾裡寫成完整檔（不靠指示詞）；
閘門（gates/brain.json、gates/fake.json）沒寫 mailbox，靠環境變數 AOS_KERNEL。產物放在 mktemp 的暫存資料夾，跑完刪掉。
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
LIB = os.path.join(HERE, "..", "..", "..", "lib")
GATE, DAEMON = os.path.join(LIB, "aos_gate.py"), os.path.join(LIB, "aos_daemon.py")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # proto8/
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def call(env, who, priority):
    """一個呼叫者：經閘門叫假腦，stdin＝思考介面的請求。回 Popen。"""
    e = dict(env, AOS_PRIORITY=json.dumps(priority)) if priority is not None else env
    p = subprocess.Popen([sys.executable, GATE, "gates/brain.json"], cwd=HERE, env=e, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p.stdin.write(json.dumps({"messages": [{"role": "user", "content": who}]}, ensure_ascii=False))
    p.stdin.close()
    return p


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def configs(tmp, log, state):
    """kernel（slots 1、額度 10 萬）／loop（每 100 ms 拍一次）／daemon 的完整設定寫進 tmp，回 daemon.json 的路徑。"""
    k = write(os.path.join(tmp, "kernel.json"), {"mailbox": os.path.join(tmp, "mb"), "state": state, "log": log,
                                                 "slots": 1, "budget": 100000, "aging_ticks": 10, "near_ms": 30000})
    lp = write(os.path.join(tmp, "loop.json"), {"inst": {"argv": [sys.executable, os.path.join(LIB, "aos_kernel_llm.py"), k],
                                                         "cwd": HERE}, "times": None, "interval_ms": 100})
    return write(os.path.join(tmp, "daemon.json"), {"children": [lp], "interval_ms": 100,
                                                    "ctl": os.path.join(tmp, "daemon.ctl.json"),
                                                    "state": os.path.join(tmp, "daemon.state.json")})


def log_since(path, start, names):
    """kernel log 第 start 行以後的；letter 名字裡的 pid 換回呼叫者名字。"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = [json.loads(x) for x in f][start:]
    except OSError:
        return []
    for r in lines:
        r["who"] = names.get(int(r["letter"].split(".")[1]), "?")
    return lines


def show(rec):
    pri = dict(rec.get("priority") or {})
    if isinstance(pri.get("deadline"), (int, float)):
        pri["deadline"] = "送出時%+d 秒" % round(pri["deadline"] - rec["sent"]) if "sent" in rec else pri["deadline"]
    pri = json.dumps(pri or None, ensure_ascii=False)
    if "error" in rec:
        say("   拍 %-3d %-10s 丟掉：%s   priority=%s" % (rec["runs"], rec["who"], rec["error"], pri))
    else:
        say("   拍 %-3d %-10s 服務 %4d ms，等了 %2d 拍   priority=%s" % (rec["runs"], rec["who"], rec["ms"], rec["waited"], pri))


def finish(procs):
    for who, p in procs:
        out, err = p.stdout.read(), p.stderr.read()
        p.wait()
        reply = (json.loads(out).get("content") if out.strip() else None) or json.loads(err)["error"]["code"]
        say("   %-10s 退出碼 %-3d %s" % (who, p.returncode, reply))


def main():
    tmp = tempfile.mkdtemp(prefix="aos-kernel-demo-")
    log, kstate = os.path.join(tmp, "kernel.log.jsonl"), os.path.join(tmp, "kernel.state.json")
    path = os.pathsep.join([os.path.join(ROOT, "bin"), os.path.join(ROOT, "demo", "bin"), os.environ.get("PATH", "")])
    env = dict(os.environ, PATH=path, PYTHONDONTWRITEBYTECODE="1", AOS_KERNEL=os.path.join(tmp, "mb"))   # 閘門的信箱
    say("暫存資料夾 %s；daemon 底下的 loop 每 100 ms 拍一次 kernel（slots 1）" % tmp)
    daemon = subprocess.Popen([sys.executable, DAEMON, configs(tmp, log, kstate)], cwd=tmp, env=env,
                              stdout=subprocess.DEVNULL)
    names = {}
    try:
        say("== 1. 級數與 deadline：X 先佔住唯一的格（腦睡 1 秒），趁這時丟五封")
        now = time.time()
        plan = [("X", None), ("A-low", "low"), ("B-normal", None), ("C-high", {"val": "high", "class": "chat"}),
                ("D-低但快到", {"val": "low", "deadline": now + 20}), ("E-已過期", {"val": "high", "deadline": now - 1})]
        procs = []
        for i, (who, pri) in enumerate(plan):
            p = call(env, who, pri)
            names[p.pid] = who
            procs.append((who, p))
            time.sleep(0.4 if i == 0 else 0.05)
        say("   丟的順序：%s" % "、".join(w for w, _ in plan))
        finish(procs)
        say("   kernel 的服務順序（log）：")
        for r in log_since(log, 0, names):
            show(r)
        n = len(log_since(log, 0, names))

        say("== 2. aging：一封 low（L），之後 normal 不斷進來（快腦 0.05 秒）；每等 10 拍升一級")
        procs = [("L-low", call(env, "快 L", "low"))]
        names[procs[0][1].pid] = "L-low"
        for i in range(14):
            p = call(env, "快 n%02d" % i, None)
            names[p.pid] = "n%02d" % i
            procs.append(("n%02d" % i, p))
            p.wait()                                       # 一封跑完才丟下一封：佇列裡永遠有新來的 normal
        procs[0][1].wait()
        for r in log_since(log, n, names):
            if r["who"] == "L-low" or r["who"] in ("n00", "n09", "n10", "n11"):
                show(r)
        order = [r["who"] for r in log_since(log, n, names)]
        say("   順序：%s" % " ".join(order))
        for _, p in procs:
            p.stdout.close()
            p.stderr.close()
        n += len(order)

        say("== 3. 報時員巢狀：boss 問「現在幾點？」→ 叫工具 clerk（另一個 agent）→ clerk 叫 clock；兩個腦都經閘門")
        frame = os.path.join(tmp, "frame")                 # 呼叫方選的 frame：frame.json 指回定義、args.json＝問題
        os.makedirs(frame)
        write(os.path.join(frame, "frame.json"), {"parent": os.path.join(HERE, "boss")})
        write(os.path.join(frame, "args.json"), {"question": "現在幾點？"})
        subprocess.run(["aos", "loop", os.path.join(HERE, "boss", "loop.json")], cwd=frame, env=env,
                       stdout=subprocess.DEVNULL, timeout=120)
        with open(os.path.join(frame, "ret.json"), encoding="utf-8") as f:
            ret = json.load(f)
        with open(os.path.join(frame, "loop/state.json"), encoding="utf-8") as f:
            ticks = json.load(f)["runs"]
        say("   boss 回：%s（boss 的 loop 敲了 %d 拍；clerk 的 frame 在 boss 的 work/1/）" % (ret.get("reply") or ret, ticks))
        for r in log_since(log, n, {}):
            say("   拍 %-3d 一次腦 %4d ms（一格一次一封；boss 等 clerk 時不佔格）" % (r["runs"], r["ms"]))
        with open(kstate, encoding="utf-8") as f:
            say("   kernel state 窗的額度：%s" % json.dumps(json.load(f)["budget"]))
    finally:
        daemon.send_signal(signal.SIGTERM)
        try:
            say("daemon 收工，退出碼 %d" % daemon.wait(15))
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait()
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
