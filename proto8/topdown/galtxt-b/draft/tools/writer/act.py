# act.py - act 格：照腦的決定動手——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案 out/<n>.txt
# 照 demo/agent-dan/act.py，只改：答案檔叫 out/<題名>.txt（題目是 <題名>.json）、錯誤開頭是 writer。工具那段原樣留（第 1 輪沒有工具）。
# round6 §1b（train/apply 的 freeze_order／patch_act 寫的資料，不在＝舊行為）：act_rules.json
#   {"after_answer": ["trim"]}＝順序已固化：交稿前一律由程式叫這些工具（{text, brief_path: cur/<n>.json#/brief}，回的 text 當答案），也不再給腦叫（brain.py 同）；
#   {"default_args": {"lint": {"brief_path": "cur/{name}.json#/brief"}}}＝腦叫工具漏了參數就補（brief 物件已給就不補 brief_path）。
#   有補或有固化呼叫＝$AOS_STACK/act.jsonl 記一行（量測用）。
import json, os, shutil, subprocess, sys


def die(code, reason):
    print("writer: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    history.append(json.loads(line))
                except ValueError as e:
                    die("HistoryBad", "history.jsonl 第 %d 行不是 JSON：%s" % (n, e))
except FileNotFoundError:
    pass
last = max((i for i, m in enumerate(history) if isinstance(m, dict) and m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
said = history[last]


def append(message):
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def note(row):
    with open(os.path.join(stack, "act.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


try:
    with open("act_rules.json", encoding="utf-8") as f:
        rules = json.load(f)
except (OSError, ValueError):
    rules = {}
rules = rules if isinstance(rules, dict) else {}
after_answer = [t for t in rules.get("after_answer") or [] if isinstance(t, str)]
default_args = rules.get("default_args") if isinstance(rules.get("default_args"), dict) else {}
with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
    name_q = f.read().strip()                  # 題目名（下面迴圈裡的 name 是工具名）

calls = said.get("tool_calls") or []
if calls:
    answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
    tools = sorted(t for t in (os.listdir("tools") if os.path.isdir("tools") else [])
                   if os.path.isfile(os.path.join("tools", t, "_tooldef.json")) and t not in after_answer
                   and os.environ.get({"lint": "GALTXT_OFF_SELF_LINT", "trim": "GALTXT_OFF_TRIM"}.get(t, "")) != "1")   # 關閉開關（同 brain.py）
    for call in calls:
        try:
            cid, name, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
        except (KeyError, TypeError):
            die("HistoryBad", "tool_calls 裡有一個沒有 id 或 function.name：%s" % json.dumps(call, ensure_ascii=False))
        if cid in answered:
            continue
        if name not in tools:
            append({"role": "tool", "tool_call_id": cid,
                    "content": "act: ToolUnknown %s（能叫的：%s）\n" % (name, "、".join(tools))})
            continue
        try:
            if not isinstance(arguments, str):
                raise ValueError("arguments 不是字串")
            args = json.loads(arguments)
        except ValueError as e:
            append({"role": "tool", "tool_call_id": cid, "content": "act: ArgumentsBad %s：%s\n" % (name, e)})
            continue
        filled = []
        if isinstance(args, dict) and isinstance(default_args.get(name), dict):
            for k, v in default_args[name].items():
                if k not in args and not (k == "brief_path" and isinstance(args.get("brief"), dict)):
                    args[k] = v.replace("{name}", name_q) if isinstance(v, str) else v
                    filled.append(k)
        if filled:
            arguments = json.dumps(args, ensure_ascii=False)
            note({"tool": name, "call": cid, "filled": filled})
        env = dict(os.environ, AOS_STACK=os.path.join(stack, name) + "/")
        try:
            r = subprocess.run(["aos-exec", "tools/" + name], input=arguments, stdout=subprocess.PIPE, text=True, env=env)
        except OSError as e:
            die("ToolFailed", "%s 起不來：%s" % (name, e))
        content = r.stdout
        if r.returncode != 0:
            print("writer: ToolFailed %s 結束碼 %d（回給腦）" % (name, r.returncode), file=sys.stderr)
            content += "%s(工具 %s 結束碼 %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, r.returncode)
        append({"role": "tool", "tool_call_id": cid, "content": content})
    sys.exit(0)

content = said.get("content") or ""
for t in after_answer:                         # 順序已固化的工具：交稿前一律由程式叫（freeze_order），失敗＝原稿照交、記一行
    if not os.path.isfile(os.path.join("tools", t, "_tooldef.json")):
        continue
    env = dict(os.environ, AOS_STACK=os.path.join(stack, t) + "/")
    arg = json.dumps({"text": content, "brief_path": "cur/%s.json#/brief" % name_q}, ensure_ascii=False)
    try:
        r = subprocess.run(["aos-exec", "tools/" + t], input=arg, stdout=subprocess.PIPE, text=True, env=env)
        got = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, ValueError):
        r, got = None, None
    if isinstance(got, dict) and isinstance(got.get("text"), str):
        content = got["text"]
        note({"tool": t, "after_answer": True, "code": 0, "counter_changes": len(got.get("changes") or [])})
    else:
        print("writer: ToolFailed %s（交稿前固化呼叫；原稿照交）" % t, file=sys.stderr)
        note({"tool": t, "after_answer": True, "code": getattr(r, "returncode", None), "counter_changes": 0})
if not content.endswith("\n"):
    content += "\n"
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name_q + ".txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", name_q + ".txt"))
shutil.move(os.path.join(ws, "cur", name_q + ".json"), os.path.join(ws, "done", name_q + ".json"))
