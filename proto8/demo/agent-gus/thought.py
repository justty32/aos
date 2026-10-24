# thought.py - 給別的程式叫「一個小念頭」的入口：AOS_STACK=<小格> aos-exec <這裡>/thought.json < step.json > 結論
# stdin：{"goal": "這一步要做到什麼"（必填）, "context": "背景摘要", "needs": [{"id": "s1", "goal": "…", "conclusion": "…"}]}
# stdout：只有結論（小念頭 out/ 裡那段答案，超過 THOUGHT_MAX_CHARS 截斷）；過程留在 $AOS_STACK/runs/NNN/（ws、stack、log.txt）。
# 小念頭＝同一隻 agent-gus（深度 THOUGHT_DEPTH+1，自己也可能再拆、再 fork）；每次呼叫開新的 runs/NNN/、不帶記憶。
# 失敗（stdin 不對、小念頭退非 0、逾時、沒交答案）：stderr 一行「agent-gus: 代號 原因」、退 1。
import json, os, signal, subprocess, sys
from shared import STACK, conclusion, die, env_int, launch, task_text

try:
    step = json.loads(sys.stdin.read())
except ValueError as e:
    die("StepBad", "stdin 不是 JSON：%s" % e)
if not isinstance(step, dict) or not isinstance(step.get("goal"), str) or not step["goal"].strip():
    die("StepBad", "要給 goal（字串）")
context, needs = step.get("context") or "", step.get("needs") or []
if not isinstance(context, str) or not isinstance(needs, list) or not all(
        isinstance(n, dict) and all(isinstance(n.get(k), str) for k in ("goal", "conclusion")) for n in needs):
    die("StepBad", "context 要是字串、needs 要是 [{id, goal, conclusion}]")
max_chars = env_int("THOUGHT_MAX_CHARS", 1500)
limit_s = env_int("THOUGHT_TIMEOUT_S", 900)

runs = os.path.join(STACK, "runs")
os.makedirs(runs, exist_ok=True)
n = 1
while True:                                         # mkdir 搶號：同一個 stack 同時被叫兩次也不撞
    cell = os.path.join(runs, "%03d" % n)
    try:
        os.mkdir(cell)
        break
    except FileExistsError:
        n += 1
budget = os.environ.get("THOUGHT_BUDGET") or os.path.join(cell, "budget")
task = task_text(step["goal"].strip(), context,
                 [(x.get("id") or "前一步", x["goal"], x["conclusion"]) for x in needs], max_chars)
p = launch(cell, "step", task, env_int("THOUGHT_DEPTH", 0) + 1, budget)


def stop(signum, frame):
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    sys.exit(128 + signum)


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    code = p.wait(limit_s)
except subprocess.TimeoutExpired:
    os.killpg(p.pid, signal.SIGTERM)
    try:
        p.wait(5)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
    die("ThoughtFailed", "逾時：超過 %d 秒，已收掉（現場在 %s）" % (limit_s, cell))
text, why = conclusion(cell, "step", code, max_chars)
if why:
    die("ThoughtFailed", why)
print(text)
