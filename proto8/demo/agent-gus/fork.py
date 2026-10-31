# fork.py - fork 格：照 steps.json 把每一步 fork 成一個小念頭（再跑一次自己這個資料夾：aos-exec .），
# 同時最多 AOS_THOUGHT_PARALLEL 個；needs 都有結論了才起那一步（前面的結論寫進它的題目）。
# 小念頭＝同一隻 agent-gus，自己的工作區與 stack 在小格 $AOS_STACK/thoughts/<id>/{ws,stack}/，深度 +1，
# 它自己也能再規劃、再 fork（深度與整棵樹的額度由 AOS_THOUGHT_DEPTH、AOS_THOUGHT_BUDGET 往下帶）。
# 小念頭交回來的只有它 out/ 裡那一段答案＝結論；全部到齊後，依規劃的順序一次接進母體的 history（一步一則）。
# 沒有要拆的步、或結論已接進 history＝什麼都不做、退 0。
# 小念頭失敗（退非 0、逾時、沒交答案）＝那一步的結論就是「失敗了：原因」，照樣接進 history、不停，讓母體的腦自己決定
# （重做、略過、照實說；10-24 代定，同 act 的「工具出錯回給腦」）；needs 它的步不起，結論寫「沒起：要的 sN 失敗了」。
# fork 自己被殺（跑到一半的步 status 還是 running）：重跑時那幾步在原本的小格裡接著跑。
import json, os, signal, subprocess, sys, time
from shared import (STEPS, STACK, append_history, conclusion, env_int, launch, read_history, read_json, task_text,
                    write_atomic)

plan = read_json(STEPS)
if not isinstance(plan, dict) or not plan.get("steps") or plan.get("recorded"):
    sys.exit(0)
steps = plan["steps"]
parallel = max(1, env_int("AOS_THOUGHT_PARALLEL", 3))
limit_s = env_int("AOS_THOUGHT_TIMEOUT_S", 900)
max_chars = env_int("AOS_THOUGHT_MAX_CHARS", 1500)
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


while True:
    changed = False
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
        elif code is not None:
            del running[i]
            finish(s, code)
    for s in steps:                                 # 上次跑到一半（fork 自己被殺）的步：照樣起，小念頭在原小格接著做
        if s["id"] in running or s["status"] in ("done", "failed"):
            continue
        bad = [n for n in s["needs"] if by_id[n]["status"] == "failed"]
        if bad:
            finish(s, None, "沒起：要先拿到 %s 的結論，但它失敗了" % "、".join(bad))
            changed = True
        elif len(running) < parallel and all(by_id[n]["status"] == "done" for n in s["needs"]):
            running[s["id"]] = start(s)
    if not running and not changed:
        break
    time.sleep(0.2)

for s in steps:                                     # 失敗的那步：stderr 留一行給人看（不停）
    if s["status"] == "failed":
        print("agent-gus: ThoughtFailed %s %s（當結論回給腦）" % (s["id"], s["error"]), file=sys.stderr)
messages = [{"role": "user", "content": "小念頭 %s 的結論（目標：%s）：\n%s" % (s["id"], s["goal"], s["conclusion"])}
            if s["status"] == "done" else
            {"role": "user", "content": "小念頭 %s 失敗了（目標：%s）：\n%s" % (s["id"], s["goal"], s["error"])}
            for s in steps]
if read_history()[-len(messages):] != messages:     # 上次接完、還沒記 recorded 就被殺：不重接
    append_history(*messages)
plan["recorded"] = True
save()
