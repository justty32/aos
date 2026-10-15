#!/usr/bin/env python3
"""proto8 fsm 的 demo：demo/fsm 本身是一個 agent 定義資料夾（C-50）；在 mktemp 建的 frame 裡跑它的 loop.json
（aos-loop 每 100 ms 拍一次 `aos agent fsm`），inbox 裡放兩封信，看兩層 state 窗怎麼變。

    python3 proto8/demo/run.py fsm                          （或直接 python3 proto8/demo/fsm/run.py）
    python3 proto8/demo/fsm/run.py brains/lmstudio.json      （換腦＝在 frame 放一份 brain.json 蓋過定義的，C-46 綁定）

frame（暫存資料夾）裡：`frame.json` {"parent": demo/fsm}（找名字往上一層）、inbox/、history、窗、work/、steps.jsonl、ret.json；
定義資料夾 demo/fsm 一個字都不寫。PATH 前面接 proto8/bin（`aos`）與 demo/bin（`aos-demo`）。跑完整個 frame 刪掉。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))            # proto8/
T0 = time.monotonic()


def env():
    """proto8 的 demo 共用：PATH 前面接 proto8/bin、demo/bin。"""
    path = os.pathsep.join([os.path.join(ROOT, "bin"), os.path.join(ROOT, "demo", "bin"), os.environ.get("PATH", "")])
    return dict(os.environ, PATH=path, PYTHONDONTWRITEBYTECODE="1")


def say(msg):
    print("[%4.1fs] %s" % (time.monotonic() - T0, msg), flush=True)


def read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def frame(tmp, brain=None):
    """把 tmp 準備成這個 agent 的 frame：frame.json 指回定義資料夾；給了 brain＝把那份腦放進 frame（綁定，蓋過定義的）。"""
    write(os.path.join(tmp, "frame.json"), {"parent": HERE})
    if brain:
        shutil.copy(os.path.join(HERE, brain), os.path.join(tmp, "brain.json"))
    os.makedirs(os.path.join(tmp, "inbox"), exist_ok=True)


def main():
    brain = sys.argv[1] if sys.argv[1:] and sys.argv[1].endswith(".json") else None
    tmp = tempfile.mkdtemp(prefix="aos-fsm-demo-")
    frame(tmp, brain)
    for name, text in (("01.txt", "你好"), ("02.txt", "現在幾點？")):
        with open(os.path.join(tmp, "inbox", name), "w", encoding="utf-8") as f:
            f.write(text)
    w = {k: os.path.join(tmp, v) for k, v in (("outer", "fsm/state.json"), ("inner", "fsm/think_state.json"))}
    say("frame（暫存資料夾）%s；inbox 放了兩封信：「你好」「現在幾點？」" % tmp)
    say("cd frame && aos loop demo/fsm/loop.json：每 100 ms 拍一次 `aos agent fsm`（照 frame.json 找到 demo/fsm/fsm.json），最多 20 次")
    say("腦：%s；thinking 格是內層 fsm（ask → review）；外層的工具只有 clerk（報時員＝另一個 agent，定義在 clerk/）" %
        (brain or "定義的 brain.json（假的腦，睡 0.4 秒）"))
    loop = subprocess.Popen(["aos", "loop", os.path.join(HERE, "loop.json")], cwd=tmp, env=env(),
                            stdout=subprocess.DEVNULL)
    seen = None
    try:
        while loop.poll() is None:
            st, sub = read(w["outer"]) or {}, read(w["inner"]) or {}
            now = (st.get("phase"), sub.get("phase"))
            if st and now != seen:                                        # 狀態變了就印一行
                seen = now
                say("外層 phase=%-8s │ 內層 phase=%-6s" % (st["phase"], sub.get("phase", "-")))
            time.sleep(0.02)
        say("aos-loop 結束，退出碼 %d（%s）" % (loop.returncode, (read(os.path.join(tmp, "loop/state.json")) or {}).get("state")))
        say("== steps.jsonl（外層 fsm 每拍吐的那行；結束那拍多一份交出去的結果）")
        with open(os.path.join(tmp, "steps.jsonl"), encoding="utf-8") as f:
            for line in f:
                say("   " + line.strip())
        say("== history.json（OpenAI messages，最後一段對話）")
        for m in read(os.path.join(tmp, "history.json")) or []:
            say("   " + json.dumps(m, ensure_ascii=False))
        work = os.path.join(tmp, "work")
        for n in sorted((x for x in os.listdir(work) if x.isdigit()), key=int) if os.path.isdir(work) else []:
            say("== work/%s/（叫 clerk 那次的 frame：args.json＝引數；clerk/ 本身沒動，history 累積在這裡）" % n)
            say("   args.taken.json：%s" % json.dumps(read(os.path.join(work, n, "args.taken.json")), ensure_ascii=False))
            for m in read(os.path.join(work, n, "history.json")) or []:
                say("   " + json.dumps(m, ensure_ascii=False))
            say("   ret.json：%s" % json.dumps(read(os.path.join(work, n, "ret.json")), ensure_ascii=False))
        say("== outbox.txt")
        with open(os.path.join(tmp, "outbox.txt"), encoding="utf-8") as f:
            for line in f:
                say("   " + line.strip())
        say("== ret.json（done 格寫的）：%s" % json.dumps(read(os.path.join(tmp, "ret.json")), ensure_ascii=False))
    finally:
        if loop.poll() is None:
            loop.kill()
            loop.wait()
        shutil.rmtree(tmp)
        say("暫存資料夾刪掉了")


if __name__ == "__main__":
    main()
