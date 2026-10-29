# plan.py - plan 格：認領題目、題目接進 history、請腦把這件事拆成幾步（steps），寫進 $AOS_STACK/steps.json。
# 已經為這題規劃過（steps.json 的 question 是這題）＝什麼都不做、退 0（重跑、或 act 跑完工具繞回來時）。
# 不拆（steps 是空的）＝這題由自己直接做：fork 格跳過、think／act 照 agent-dan 做。
# 深度到上限、或整棵樹的小念頭額度不夠，不問腦、直接不拆（省一次腦）。
# 腦的回覆不是規劃（解不出帶 steps 的 JSON 物件：直接回答了、或說做不到）＝當不拆（direct "prose"），不算 PlanBad：
# 規劃時不送 tools，真模型（10-24 實測）常回「沒有 Python 工具可用」的散文；think 格會帶 tools 再問一次。
# 是規劃但寫錯（steps 不是陣列、id、needs、步數不對）＝照舊 PlanBad。
import fcntl, json, os, re, sys, uuid
from shared import (STACK, STEPS, append_history, ask, claim, die, env_int, read_history, read_json, system,
                    write_atomic)

PROMPT = """【規劃】先別回答，先想這件事要不要拆成幾步、交給幾個「小念頭」分頭去做。
小念頭看不到這段對話，只看到你給的 context（背景摘要）和它自己那一步的 goal，做完只帶回一段結論。
只回一個 JSON 物件，不要別的字：
{"context": "給每個小念頭的背景摘要（它們需要知道的事、限制）",
 "steps": [{"id": "s1", "goal": "這一步要做到什麼、帶回什麼結論", "needs": []},
           {"id": "s2", "goal": "...", "needs": ["s1"]}]}
規則：
- 一步就能做完、或用工具直接做比較快的事，回 {"context": "", "steps": []}，由你自己直接做。
- 最多 %d 步；id 只用小寫英數與底線；needs 列出這一步要先拿到哪幾步的結論（沒有就空陣列），不能繞圈。
- 沒有 needs 的步會同時做；彙整全部結論、寫最後的回答是你自己的事，不要拆成一步。
（你現在在第 %d 層；母體是第 0 層。）"""
ID = re.compile(r"^[a-z0-9_]{1,16}$")


def parse(content, limit):
    """腦的回覆 → (context, steps)；不合就 PlanBad。"""
    text = (content or "").strip()
    m = re.search(r"\{.*\}", text, re.S)          # 容許 ```json 圍欄或前後多話
    try:
        plan = json.loads(m.group(0)) if m else None
    except ValueError:
        plan = None
    if not isinstance(plan, dict) or "steps" not in plan:
        return None, []                            # 不是規劃（腦直接回答了）＝當不拆（10-24 真腦實測）
    if not isinstance(plan["steps"], list):
        die("PlanBad", "steps 要是陣列")
    context = plan.get("context") or ""
    if not isinstance(context, str):
        die("PlanBad", "context 要是字串")
    steps, seen = [], set()
    for s in plan["steps"]:
        if not isinstance(s, dict) or not isinstance(s.get("id"), str) or not ID.match(s["id"]):
            die("PlanBad", "step 的 id 不對：%r" % (s,))
        if s["id"] in seen:
            die("PlanBad", "id 重複：%s" % s["id"])
        if not isinstance(s.get("goal"), str) or not s["goal"].strip():
            die("PlanBad", "%s 沒有 goal" % s["id"])
        needs = s.get("needs") or []
        if not isinstance(needs, list) or not all(isinstance(n, str) for n in needs):
            die("PlanBad", "%s 的 needs 要是字串陣列" % s["id"])
        seen.add(s["id"])
        steps.append({"id": s["id"], "goal": s["goal"].strip(), "needs": needs, "status": "todo"})
    if len(steps) > limit:
        die("PlanBad", "拆成 %d 步，超過上限 %d" % (len(steps), limit))
    for s in steps:
        for n in s["needs"]:
            if n not in seen or n == s["id"]:
                die("PlanBad", "%s 的 needs 指到不存在的步：%s" % (s["id"], n))
    done, left = set(), list(steps)                # 繞圈：一層層拿掉 needs 都滿足的，拿不完＝有圈
    while left:
        ready = [s for s in left if set(s["needs"]) <= done]
        if not ready:
            die("PlanBad", "needs 繞圈：%s" % ", ".join(s["id"] for s in left))
        done |= {s["id"] for s in ready}
        left = [s for s in left if s["id"] not in done]
    return context, steps


def reserve(budget, plan_id, ids, total):
    """整棵樹的額度：budget/ 裡一個檔＝一個已經算進去的小念頭；拿鎖數一數，夠才建。回 True＝拿到了。"""
    os.makedirs(budget, exist_ok=True)
    with open(os.path.join(budget, ".flock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        used = [n for n in os.listdir(budget) if not n.startswith(".")]
        if len(used) + len(ids) > total:
            return False
        for i in ids:
            open(os.path.join(budget, "%s-%s" % (plan_id, i)), "w").close()
        return True


name, question = claim()
old = read_json(STEPS)
if isinstance(old, dict) and old.get("question") == name:
    sys.exit(0)                                     # 這題規劃過了

history = read_history()
if not history or history[-1].get("role") not in ("user", "tool"):
    append_history({"role": "user", "content": question})
    history.append({"role": "user", "content": question})

depth, max_depth = env_int("THOUGHT_DEPTH", 0), env_int("THOUGHT_MAX_DEPTH", 2)
max_steps, total = env_int("THOUGHT_MAX_STEPS", 4), env_int("THOUGHT_MAX_TOTAL", 10)
plan_id = uuid.uuid4().hex[:8]
budget = os.environ.get("THOUGHT_BUDGET") or os.path.join(STACK, "budgets", plan_id)   # 母體：一題一份額度
os.makedirs(budget, exist_ok=True)
remaining = total - len([n for n in os.listdir(budget) if not n.startswith(".")])

context, steps, why, reply = "", [], None, None
if depth >= max_depth:
    why = "depth"                                   # 到底了，直接做
elif remaining < 2:
    why = "budget"
elif not os.environ.get("AOS_BRAIN_URL"):          # 假腦：第 0 層拆兩步（s2 要 s1 的結論），其他層不拆
    if depth == 0:
        context = "題目：" + question.strip()
        steps = [{"id": "s1", "goal": "說出題目的重點", "needs": [], "status": "todo"},
                 {"id": "s2", "goal": "根據重點給一個答案", "needs": ["s1"], "status": "todo"}]
    why = None if steps else "brain"
else:
    msg = ask("plan", system() + [{"role": "system", "content": PROMPT % (min(max_steps, remaining), depth)}] + history)
    reply = msg.get("content")
    context, steps = parse(reply, min(max_steps, remaining))
    if context is None:                             # 回的是散文、不是規劃：自己做（think 會帶 tools 再問一次）
        context, why = "", "prose"
    elif len(steps) == 1:                             # 只拆一步＝白 fork 一次，當成不拆
        steps, why = [], "one"
    elif not steps:
        why = "brain"
if steps and not reserve(budget, plan_id, [s["id"] for s in steps], total):
    steps, why = [], "budget"                       # 同時有別的念頭搶走額度：不拆、自己做

write_atomic(STEPS, json.dumps({"question": name, "plan_id": plan_id, "depth": depth, "budget": budget,
                                "direct": why, "context": context, "steps": steps, "reply": reply,
                                "recorded": False}, ensure_ascii=False, indent=1) + "\n")
