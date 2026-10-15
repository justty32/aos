#!/usr/bin/env python3
"""proto8 fsm 的 demo：aos-loop 每 100 ms 拍一次 aos-fsm（agent.json），inbox 裡放兩封信，看兩層 state 窗怎麼變。

    python3 proto8/demo/run.py fsm        （或直接 python3 proto8/demo/fsm/run.py）

產物（inbox、work、outbox、窗、steps.jsonl）都放在 mktemp 建的暫存資料夾，跑完整個刪掉。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOOP = os.path.join(HERE, "..", "..", "lib", "aos_loop.py")
T0 = time.monotonic()


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    tmp = tempfile.mkdtemp(prefix="aos-fsm-demo-")
    for d in ("inbox", "work"):
        os.makedirs(os.path.join(tmp, d))
    for name, text in (("01.txt", "你好"), ("02.txt", "現在幾點？")):
        with open(os.path.join(tmp, "inbox", name), "w", encoding="utf-8") as f:
            f.write(text)
    w = {k: os.path.join(tmp, v) for k, v in (("state", "agent.state.json"), ("think", "think.state.json"),
                                               ("steps", "steps.jsonl"), ("loop_state", "loop.state.json"))}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", DEMO_DIR=tmp, DEMO_STATE=w["state"], DEMO_THINK_STATE=w["think"],
               DEMO_LOCK=os.path.join(tmp, "agent.lock"), DEMO_STEPS=w["steps"],
               DEMO_HISTORY=os.path.join(tmp, "work", "history.json"), DEMO_WORK=os.path.join(tmp, "work"),
               DEMO_LOOP_CTL=os.path.join(tmp, "loop.ctl.json"), DEMO_LOOP_STATE=w["loop_state"])
    say("暫存資料夾 %s；inbox 放了兩封信：「你好」「現在幾點？」" % tmp)
    say("aos-loop 拍 aos-fsm 10 次、每次隔 100 ms；thinking 格是內層 fsm（ask → review），ask 叫腦（agent.json 的 brain：假的腦，睡 0.4 秒）")
    say("外層的工具只有 clerk（報時員＝另一個 agent，定義在 clerk/）：問時間就得問它，它自己再用 clock")
    loop = subprocess.Popen([sys.executable, LOOP, "loop.json"], cwd=HERE, env=env, stdout=subprocess.DEVNULL)
    seen = None
    try:
        while loop.poll() is None:
            st, sub = read(w["state"]) or {}, read(w["think"]) or {}
            now = (st.get("phase"), st.get("step"), sub.get("phase"))
            if st and st.get("running") is False and now != seen:        # 只印每拍跑完的樣子（跑格中 running 是 true）
                seen = now
                say("外層 phase=%-8s step=%s │ 內層 phase=%-6s │ data=%s"
                    % (st["phase"], st["step"], sub.get("phase", "-"),
                       json.dumps(st.get("data"), ensure_ascii=False)))
            time.sleep(0.02)
        say("aos-loop 結束，退出碼 %d" % loop.returncode)
        say("== steps.jsonl（外層 fsm 每拍吐的那行）")
        with open(w["steps"], encoding="utf-8") as f:
            for line in f:
                say("   " + line.strip())
        say("== work/history.json（OpenAI messages，最後一段對話）")
        for m in read(os.path.join(tmp, "work", "history.json")) or []:
            say("   " + json.dumps(m, ensure_ascii=False))
        for fr in sorted(n for n in os.listdir(os.path.join(tmp, "work")) if n.startswith("ask-")):
            say("== work/%s/history.json（報時員 clerk 的 frame：clerk/ 本身沒動，history 累積在這裡）" % fr)
            for m in read(os.path.join(tmp, "work", fr, "history.json")) or []:
                say("   " + json.dumps(m, ensure_ascii=False))
        say("== outbox.txt")
        with open(os.path.join(tmp, "outbox.txt"), encoding="utf-8") as f:
            for line in f:
                say("   " + line.strip())
    finally:
        if loop.poll() is None:
            loop.kill()
            loop.wait()
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
