# act.py - act 格：照腦的決定動手（同 agent-dan）——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；
# 沒有就把 content 寫成答案 $AOS_WS/out/<題名>、題目 cur/ → done/，這題的 steps.json 收進 $AOS_STACK/plans/<plan_id>.json。
# 工具的介面：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的 stack＝$AOS_STACK/<名>/（P-17）。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑。任何錯：stderr 一行、退 1、history 不接（P-20）。
# 工具退非 0 不停、回給腦（10-24 遷移：run_python 改掛 lib/base 後「模型的錯」也退 1——lib/README「工具只報錯、停不停由 agent 決定」，
# 這隻照舊讓腦自己改；做法同 agent-pip：stdout 照收、尾巴加結束碼，人在 stderr 看得到）。
import json, os, shutil, subprocess, sys
from shared import STACK, STEPS, WS, append_history, die, read_history, read_json, write_atomic

history = read_history()
last = max((i for i, m in enumerate(history) if isinstance(m, dict) and m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
said = history[last]

calls = said.get("tool_calls") or []
if calls:
    answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
    tools = sorted(t for t in (os.listdir("tools") if os.path.isdir("tools") else [])
                   if os.path.isfile(os.path.join("tools", t, "tool.json")))
    for call in calls:
        try:
            cid, name, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
        except (KeyError, TypeError):
            die("HistoryBad", "tool_calls 裡有一個沒有 id 或 function.name：%s" % json.dumps(call, ensure_ascii=False))
        if cid in answered:
            continue
        if name not in tools:           # 名字只認 tools/ 底下有 tool.json 的資料夾（也擋掉 ../ 之類）
            die("ToolUnknown", name)
        if not isinstance(arguments, str):
            die("ArgumentsBad", "%s：arguments 不是字串" % name)
        try:
            json.loads(arguments)
        except ValueError as e:
            die("ArgumentsBad", "%s：%s" % (name, e))
        env = dict(os.environ, AOS_STACK=os.path.join(STACK, name) + "/")
        try:
            r = subprocess.run(["aos-exec", "tools/" + name], input=arguments, stdout=subprocess.PIPE,
                               text=True, env=env)
        except OSError as e:
            die("ToolFailed", "%s 起不來：%s" % (name, e))
        content = r.stdout
        if r.returncode != 0:           # 回給腦、不停
            print("agent-gus: ToolFailed %s 結束碼 %d（回給腦）" % (name, r.returncode), file=sys.stderr)
            content += "%s(工具 %s 結束碼 %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, r.returncode)
        append_history({"role": "tool", "tool_call_id": cid, "content": content})
    sys.exit(0)

with open(os.path.join(STACK, "current.txt"), encoding="utf-8") as f:
    name = f.read().strip()
content = said.get("content") or ""
if not content.endswith("\n"):
    content += "\n"
os.makedirs(os.path.join(WS, "out"), exist_ok=True)
os.makedirs(os.path.join(WS, "done"), exist_ok=True)
write_atomic(os.path.join(WS, "out", name), content)
plan = read_json(STEPS)
if isinstance(plan, dict):                        # 這題的規劃收起來（下一題重新規劃）；留著給人看
    os.makedirs(os.path.join(STACK, "plans"), exist_ok=True)
    os.replace(STEPS, os.path.join(STACK, "plans", "%s.json" % plan.get("plan_id", "x")))
shutil.move(os.path.join(WS, "cur", name), os.path.join(WS, "done", name))
