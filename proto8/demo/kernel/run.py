#!/usr/bin/env python3
"""proto8 LLM kernel 的 demo：aos-daemon 底下一個 aos-loop 每 100 ms 拍一次 kernel（aos_gate_kernel.py），
呼叫者都經閘門（aos_gate.py）叫同一顆假腦（睡 1 秒），看 kernel 照什麼順序服務。

    python3 proto8/demo/run.py kernel        （或直接 python3 proto8/demo/kernel/run.py）

三段：(1) 級數／deadline：先一封佔住唯一的格，再同時丟 low、normal、high、deadline 快到、deadline 已過；
(2) aging：一封 low 跟一串不斷進來的 normal（快腦）；(3) 報時員巢狀（boss 問 clerk、clerk 查 clock），
兩個 agent 的腦都包了閘門、一格就夠。產物放在 mktemp 的暫存資料夾，跑完刪掉。
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
LIB = os.path.join(HERE, "..", "..", "lib")
GATE, DAEMON = os.path.join(LIB, "aos_gate.py"), os.path.join(LIB, "aos_daemon.py")
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def call(env, who, priority):
    """一個呼叫者：經閘門叫假腦，stdin＝思考介面的請求。回 Popen。"""
    e = dict(env, AOS_PRIORITY=json.dumps(priority)) if priority is not None else env
    p = subprocess.Popen([sys.executable, GATE, "gate.json"], cwd=HERE, env=e, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p.stdin.write(json.dumps({"messages": [{"role": "user", "content": who}]}, ensure_ascii=False))
    p.stdin.close()
    return p


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
        say("   tick %-3d %-10s 丟掉：%s   priority=%s" % (rec["tick"], rec["who"], rec["error"], pri))
    else:
        say("   tick %-3d %-10s 服務 %4d ms，等了 %2d 拍   priority=%s" % (rec["tick"], rec["who"], rec["ms"], rec["waited"], pri))


def finish(procs):
    for who, p in procs:
        out, err = p.stdout.read(), p.stderr.read()
        p.wait()
        reply = (json.loads(out).get("content") if out.strip() else None) or json.loads(err)["error"]["code"]
        say("   %-10s 退出碼 %-3d %s" % (who, p.returncode, reply))


def main():
    tmp = tempfile.mkdtemp(prefix="aos-kernel-demo-")
    log = os.path.join(tmp, "kernel.log.jsonl")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", AOS_KERNEL=os.path.join(tmp, "mb"), DEMO_KERNEL_LOG=log,
               DEMO_KERNEL_STATE=os.path.join(tmp, "kernel.state.json"),
               DEMO_DAEMON_CTL=os.path.join(tmp, "daemon.ctl.json"), DEMO_DAEMON_STATE=os.path.join(tmp, "daemon.state.json"))
    say("暫存資料夾 %s；daemon 底下的 loop 每 100 ms 拍一次 kernel（slots 1）" % tmp)
    daemon = subprocess.Popen([sys.executable, DAEMON, "daemon.json"], cwd=HERE, env=env, stdout=subprocess.DEVNULL)
    names = {}
    try:
        say("== 1. 級數與 deadline：X 先佔住唯一的格（腦睡 1 秒），趁這時丟五封")
        now = time.time()
        plan = [("X", None), ("A-low", "low"), ("B-normal", None), ("C-high", {"level": "high", "class": "chat"}),
                ("D-低但快到", {"level": "low", "deadline": now + 20}), ("E-已過期", {"level": "high", "deadline": now - 1})]
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
        sys.path.insert(0, LIB)
        os.environ.update(AOS_KERNEL=env["AOS_KERNEL"], PYTHONDONTWRITEBYTECODE="1")
        import aos_agent_call
        out = aos_agent_call.Agent(os.path.join(HERE, "boss", "agent.json")).call(
            os.path.join(tmp, "frame"), history=[{"role": "user", "content": "現在幾點？"}], cwd=tmp)
        say("   boss 回：%s（敲了 %d 拍）" % (out["reply"], out["ticks"]))
        for r in log_since(log, n, {}):
            say("   tick %-3d 一次腦 %4d ms（一格一次一封；boss 等 clerk 時不佔格）" % (r["tick"], r["ms"]))
        with open(env["DEMO_KERNEL_STATE"], encoding="utf-8") as f:
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
