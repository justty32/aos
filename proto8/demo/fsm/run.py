#!/usr/bin/env python3
"""proto8 fsm 的 demo：aos-loop 每 100 ms 拍一次 aos-fsm（agent.json），inbox 裡放兩封信，看兩層 state 窗怎麼變。

    python3 proto8/demo/run.py fsm        （或直接 python3 proto8/demo/fsm/run.py）

產物（inbox、work、outbox、窗、steps.jsonl）都放在 mktemp 建的暫存資料夾，跑完整個刪掉。
不靠指示詞：repo 裡的 agent.json、think/fsm.json 只寫定義（表、brain、tools、system）；執行期的 key（state、lock、
history、work、內層的 state）由 `bind()` 填進暫存資料夾裡的副本 agent.json，loop 的設定也在那裡寫成完整檔。
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


def write(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


def _cell(v, cfg):
    """格（TARGET 字串、內嵌 inst、或 {target, next}）→ 內嵌 inst，`stdin` 指 cfg（10-15 收工後 fsm 不再餵格 stdin，
    格的設定由自己的 inst 的 stdin 給；第二批改成定義資料夾時這段拿掉）。TARGET 從 demo 資料夾算。"""
    nxt = None
    if isinstance(v, dict) and "target" in v:
        v, nxt = v["target"], v.get("next")
    if isinstance(v, str):
        path = os.path.join(HERE, v)
        if os.path.isdir(path):
            path = os.path.join(path, "inst.json")
        with open(path, encoding="utf-8") as f:
            v = json.load(f)
    v = dict(v, stdin=cfg)
    return {"target": v, "next": nxt} if nxt else v


def bind(tmp):
    """把 demo 的定義綁到暫存資料夾 tmp：寫 tmp/agent.json（＝repo 的 agent.json＋state、history、work）。
    格都攤成內嵌 inst、`stdin` 指 tmp/agent.json（格從這裡拿 brain、tools、history…）；thinking 格＝內層 fsm，
    內層表 think/fsm.json 也攤成 tmp/think.json（state 窗指進 tmp）。回 tmp/agent.json 的路徑。
    格的 argv 相對路徑照舊從 demo 資料夾算（跑的時候 cwd＝demo 資料夾）。"""
    agent = os.path.join(tmp, "agent.json")
    with open(os.path.join(HERE, "agent.json"), encoding="utf-8") as f:
        doc = json.load(f)
    with open(os.path.join(HERE, "think", "fsm.json"), encoding="utf-8") as f:
        inner = json.load(f)
    inner["states"] = {k: _cell(os.path.join("think", v) if isinstance(v, str) else
                                dict(v, target=os.path.join("think", v["target"])) if isinstance(v.get("target"), str) else v,
                                agent)
                       for k, v in inner["states"].items()}
    inner["state"] = os.path.join(tmp, "think.state.json")
    write(os.path.join(tmp, "think.json"), inner)
    states = {k: _cell(v, agent) for k, v in doc["states"].items() if k != "thinking"}
    states["thinking"] = {"argv": ["python3", "../../lib/aos_fsm.py", os.path.join(tmp, "think.json")]}
    doc.update(states=states, state=os.path.join(tmp, "agent.state.json"),
               history=os.path.join(tmp, "work", "history.json"), work=os.path.join(tmp, "work"))
    return write(agent, doc)


def main():
    tmp = tempfile.mkdtemp(prefix="aos-fsm-demo-")
    for d in ("inbox", "work"):
        os.makedirs(os.path.join(tmp, d))
    for name, text in (("01.txt", "你好"), ("02.txt", "現在幾點？")):
        with open(os.path.join(tmp, "inbox", name), "w", encoding="utf-8") as f:
            f.write(text)
    w = {k: os.path.join(tmp, v) for k, v in (("state", "agent.state.json"), ("think", "think.state.json"),
                                               ("steps", "steps.jsonl"), ("loop_state", "loop.state.json"))}
    agent = bind(tmp)
    loop_json = write(os.path.join(tmp, "loop.json"), {
        "inst": {"argv": ["python3", "../../lib/aos_fsm.py", agent], "stdout": w["steps"], "stdout_append": True,
                 "timeout_ms": 20000},
        "ctl": os.path.join(tmp, "loop.ctl.json"), "state": w["loop_state"], "times": 10, "interval_ms": 100})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", DEMO_DIR=tmp)
    say("暫存資料夾 %s；inbox 放了兩封信：「你好」「現在幾點？」" % tmp)
    say("aos-loop 拍 aos-fsm 10 次、每次隔 100 ms；thinking 格是內層 fsm（ask → review），ask 叫腦（agent.json 的 brain：假的腦，睡 0.4 秒）")
    say("外層的工具只有 clerk（報時員＝另一個 agent，定義在 clerk/）：問時間就得問它，它自己再用 clock")
    loop = subprocess.Popen([sys.executable, LOOP, loop_json], cwd=HERE, env=env, stdout=subprocess.DEVNULL)
    seen = None
    try:
        while loop.poll() is None:
            st, sub = read(w["state"]) or {}, read(w["think"]) or {}
            now = (st.get("phase"), sub.get("phase"))
            if st and now != seen:                                        # 狀態變了就印一行
                seen = now
                say("外層 phase=%-8s │ 內層 phase=%-6s" % (st["phase"], sub.get("phase", "-")))
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
