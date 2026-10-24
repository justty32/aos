# fork.py - fork 格：照 steps.json 把每一步 fork 成一個小念頭（再跑一次自己這個資料夾：aos-exec .），
# 同時最多 THOUGHT_PARALLEL 個；needs 都有結論了才起那一步（前面的結論寫進它的題目）。
# 小念頭＝同一隻 agent-gus，自己的工作區與 stack 在小格 $AOS_STACK/thoughts/<id>/{ws,stack}/，深度 +1，
# 它自己也能再規劃、再 fork（深度與整棵樹的額度由 THOUGHT_DEPTH、THOUGHT_BUDGET 往下帶）。
# 小念頭交回來的只有它 out/ 裡那一段答案＝結論；全部到齊後，依規劃的順序一次接進母體的 history（一步一則）。
# 沒有要拆的步、或結論已接進 history＝什麼都不做、退 0。
# 有小念頭失敗（退非 0、逾時、沒交答案）：等同一批其他的跑完、記下，stderr 一行 ThoughtFailed、退 1；
# 人修好再跑，已有結論的不重做，失敗的那個在它原本的小格裡接著跑（它自己的 state 還在）。
import json, os, signal, subprocess, sys, time
from shared import (STEPS, STACK, append_history, conclusion, die, env_int, launch, read_history, read_json, task_text,
                    write_atomic)

plan = read_json(STEPS)
if not isinstance(plan, dict) or not plan.get("steps") or plan.get("recorded"):
    sys.exit(0)
steps = plan["steps"]
parallel = max(1, env_int("THOUGHT_PARALLEL", 3))
limit_s = env_int("THOUGHT_TIMEOUT_S", 900)
max_chars = env_int("THOUGHT_MAX_CHARS", 1500)
by_id = {s["id"]: s for s in steps}


def save():
    write_atomic(STEPS, json.dumps(plan, ensure_ascii=False, indent=1) + "\n")


def cell(s):
    return os.path.join(STACK, "thoughts", s["id"])


def start(s):
    needs = [(n, by_id[n]["goal"], by_id[n]["conclusion"]) for n in s["needs"]]
    p = launch(cell(s), s["id"], task_text(s["goal"], plan.get("context") or "", needs, max_chars),
               plan["depth"] + 1, plan["budget"])
    s["status"], s["started_at"] = "running", time.time()
    save()
    return p


running = {}                                        # id → Popen


def stop_all(signum, frame):                       # 自己被收（fsm 的 timeout_ms、Ctrl-C）：先把小念頭整群收掉
    for p in running.values():
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    sys.exit(128 + signum)


signal.signal(signal.SIGTERM, stop_all)
signal.signal(signal.SIGINT, stop_all)


def finish(s, code, why=None):
    s.pop("started_at", None)
    text = None
    if why is None:
        text, why = conclusion(cell(s), s["id"], code, max_chars)
    if why:
        s["status"], s["error"] = "failed", why
    else:
        s["status"], s["conclusion"] = "done", text
        s.pop("error", None)
    save()


failed = False                                      # 上次失敗或跑到一半（fork 自己被殺）的步：照樣起，小念頭在原小格接著做
while True:
    for i, p in list(running.items()):
        s = by_id[i]
        code = p.poll()
        if code is None and time.time() - s["started_at"] > limit_s:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            del running[i]
            finish(s, None, "逾時：超過 %d 秒，已收掉（現場在 %s）" % (limit_s, cell(s)))
            failed = True
        elif code is not None:
            del running[i]
            finish(s, code)
            failed = failed or s["status"] == "failed"
    if not failed:
        done = {s["id"] for s in steps if s["status"] == "done"}
        for s in steps:
            if len(running) >= parallel:
                break
            if s["id"] not in running and s["status"] != "done" and set(s["needs"]) <= done:
                running[s["id"]] = start(s)
    if not running:
        break
    time.sleep(0.2)

bad = [s for s in steps if s["status"] == "failed"]
if bad:
    die("ThoughtFailed", "；".join("%s %s" % (s["id"], s["error"]) for s in bad))

messages = [{"role": "user", "content": "小念頭 %s 的結論（目標：%s）：\n%s" % (s["id"], s["goal"], s["conclusion"])}
            for s in steps]
if read_history()[-len(messages):] != messages:     # 上次接完、還沒記 recorded 就被殺：不重接
    append_history(*messages)
plan["recorded"] = True
save()
