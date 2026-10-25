# act.py - act 格：照腦的決定動手——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案 out/<n>.txt
# 照 demo/agent-dan/act.py，只改：答案檔叫 out/<題名>.txt（題目是 <題名>.json）、錯誤開頭是 writer。工具那段原樣留（第 1 輪沒有工具）。
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
        if name not in tools:
            append({"role": "tool", "tool_call_id": cid,
                    "content": "act: ToolUnknown %s（能叫的：%s）\n" % (name, "、".join(tools))})
            continue
        try:
            if not isinstance(arguments, str):
                raise ValueError("arguments 不是字串")
            json.loads(arguments)
        except ValueError as e:
            append({"role": "tool", "tool_call_id": cid, "content": "act: ArgumentsBad %s：%s\n" % (name, e)})
            continue
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

with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
    name = f.read().strip()
content = said.get("content") or ""
if not content.endswith("\n"):
    content += "\n"
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name + ".txt")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", name + ".txt"))
shutil.move(os.path.join(ws, "cur", name + ".json"), os.path.join(ws, "done", name + ".json"))
