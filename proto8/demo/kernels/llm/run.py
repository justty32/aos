#!/usr/bin/env python3
"""proto8 LLM kernel 的 demo：aos-daemon 底下一個 aos-loop 每 100 ms 拍一次 kernel（aos_kernel_llm.py），
呼叫者都經閘門（aos_gate.py）叫同一顆假腦（睡 1 秒），看 kernel 照什麼順序服務（順序＝呼叫者回來的順序；kernel 沒有 log 檔）。

    python3 proto8/demo/run.py kernels/llm    （或直接 python3 proto8/demo/kernels/llm/run.py）

三段：(1) 級數／deadline：先一封佔住唯一的格，再同時丟 low、normal、high、deadline 快到、deadline 已過；
(2) aging：一封 low 跟一串不斷進來的 normal（快腦）；(3) 報時員巢狀（boss 問 clerk、clerk 查 clock）：boss＝定義資料夾 boss/
（腦 brain.json＝經閘門叫假腦）；clerk 借 demo/fsm/clerk 的定義、用它自己定義的腦（不經閘門；demo 不示範上層伸手進下層的 frame，
10-15 深夜 KISS 批次 1）——boss 的腦一格就夠，boss 等 clerk 時不佔格。kernel／loop／daemon 的設定在暫存資料夾裡寫成完整檔（不靠指示詞）；
閘門（gates/brain.json、gates/fake.json）的 mailbox 寫成 {"$env": "AOS_KERNEL"}（demo 省字的便利，閘門程式自己不認環境變數）；
priority 用閘門的 --priority 旗標給。產物放在 mktemp 的暫存資料夾，跑完刪掉。
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
    flags = ["--priority", json.dumps(priority)] if priority is not None else []
    p = subprocess.Popen([sys.executable, GATE, "gates/brain.json"] + flags, cwd=HERE, env=env, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    p.stdin.write(json.dumps({"messages": [{"role": "user", "content": who}]}, ensure_ascii=False))
    p.stdin.close()
    return p


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def configs(tmp, state):
    """kernel（slots 1、額度 10 萬）／loop（每 100 ms 拍一次）／daemon 的完整設定寫進 tmp，回 daemon.json 的路徑。"""
    k = write(os.path.join(tmp, "kernel.json"), {"mailbox": os.path.join(tmp, "mb"), "state": state,
                                                 "slots": 1, "budget": 100000, "aging_ticks": 10, "near_ms": 30000})
    lp = write(os.path.join(tmp, "loop.json"), {"inst": {"argv": [sys.executable, os.path.join(LIB, "aos_kernel_llm.py"), k],
                                                         "cwd": HERE}, "times": None, "interval_ms": 100})
    return write(os.path.join(tmp, "daemon.json"), {"children": [lp], "interval_ms": 100,
                                                    "ctl": os.path.join(tmp, "daemon.ctl.json"),
                                                    "state": os.path.join(tmp, "daemon.state.json")})


def finish(procs):
    """等每個呼叫者回來，照回來的先後印（slots 1：回來的順序＝kernel 服務的順序）。"""
    left = list(procs)
    while left:
        for who, p in list(left):
            if p.poll() is None:
                continue
            left.remove((who, p))
            out, err = p.stdout.read(), p.stderr.read()
            p.stdout.close()
            p.stderr.close()
            reply = (json.loads(out).get("content") if out.strip() else None) or json.loads(err)["error"]["code"]
            say("   %-10s 回來了：退出碼 %-3d %s" % (who, p.returncode, reply))
        time.sleep(0.02)


def main():
    tmp = tempfile.mkdtemp(prefix="aos-kernel-demo-")
    kstate = os.path.join(tmp, "kernel.state.json")
    path = os.pathsep.join([os.path.join(ROOT, "bin"), os.path.join(ROOT, "demo", "bin"), os.environ.get("PATH", "")])
    env = dict(os.environ, PATH=path, PYTHONDONTWRITEBYTECODE="1", AOS_KERNEL=os.path.join(tmp, "mb"))   # 閘門的信箱
    say("暫存資料夾 %s；daemon 底下的 loop 每 100 ms 拍一次 kernel（slots 1）" % tmp)
    daemon = subprocess.Popen([sys.executable, DAEMON, configs(tmp, kstate)], cwd=tmp, env=env,
                              stdout=subprocess.DEVNULL)
    try:
        say("== 1. 級數與 deadline：X 先佔住唯一的格（腦睡 1 秒），趁這時丟五封")
        now = time.time()
        plan = [("X", None), ("A-low", "low"), ("B-normal", None), ("C-high", {"val": "high", "class": "chat"}),
                ("D-低但快到", {"val": "low", "deadline": now + 20}), ("E-已過期", {"val": "high", "deadline": now - 1})]
        procs = []
        for i, (who, pri) in enumerate(plan):
            procs.append((who, call(env, who, pri)))
            time.sleep(0.4 if i == 0 else 0.05)
        say("   丟的順序：%s（E 的 deadline 已過、D 的剩 20 秒＝插隊）" % "、".join(w for w, _ in plan))
        say("   回來的順序（＝kernel 服務的順序，slots 1）：")
        finish(procs)

        say("== 2. aging：一封 low（L），之後 normal 不斷進來（快腦 0.05 秒）；每等 10 拍升一級")
        low = call(env, "快 L", "low")
        after = None
        for i in range(14):
            p = call(env, "快 n%02d" % i, None)
            p.wait()                                       # 一封跑完才丟下一封：佇列裡永遠有新來的 normal
            p.stdout.close()
            p.stderr.close()
            if after is None and low.poll() is not None:
                after = i
        low.wait()
        low.stdout.close()
        low.stderr.close()
        say("   L-low 在 n%02d 回來之後才回來（沒 aging＝永遠輪不到；等滿 10 拍升成 normal 就輪到）" % after)

        say("== 3. 報時員巢狀：boss 問「現在幾點？」→ 叫工具 clerk（另一個 agent）→ clerk 叫 clock；boss 的腦經閘門、clerk 用自己的")
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
        say("   boss 回：%s（boss 的 loop 敲了 %d 拍；clerk 的 frame 在 boss 的 work/1/；boss 等 clerk 時不佔格）" % (ret.get("reply") or ret, ticks))
        with open(kstate, encoding="utf-8") as f:
            st = json.load(f)
        say("   kernel state 窗：served %d、額度 %s" % (st["served"], json.dumps(st["budget"])))
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
