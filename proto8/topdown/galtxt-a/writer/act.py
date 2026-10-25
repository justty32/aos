# act.py - act 格（抄 agent-dan，只改錯誤訊息開頭）：照腦的決定動手——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案
# 工具的介面：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的 stack＝$AOS_STACK/<名>/（P-17）。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑（只補沒回的）。
# 叫工具出的問題回給腦、不停（10-24 起，同 agent-pip）：工具退非 0（stdout 照收、尾巴加結束碼）、叫了沒有的工具、arguments 不是 JSON，
# 都接成一則 tool 訊息讓腦自己決定（停下的話重跑會再叫同一個、永遠卡住）；工具的 stderr 不讀（C-52、C-53）。
# 只有自己這層的錯（環境壞了：沒 stack、history 壞、aos-exec 起不來）才停：stderr 一行、退 1、history 不接（P-20）。
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
        if name not in tools:           # 名字只認 tools/ 底下有 tool.json 的資料夾（也擋掉 ../ 之類）
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
            r = subprocess.run(["aos-exec", "tools/" + name], input=arguments, stdout=subprocess.PIPE,
                               text=True, env=env)      # stderr 不吞：工具自己的錯原樣往上
        except OSError as e:
            die("ToolFailed", "%s 起不來：%s" % (name, e))
        content = r.stdout
        if r.returncode != 0:           # 回給腦、不停；人在 stderr 看得到
            print("writer: ToolFailed %s 結束碼 %d（回給腦）" % (name, r.returncode), file=sys.stderr)
            content += "%s(工具 %s 結束碼 %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, r.returncode)
        append({"role": "tool", "tool_call_id": cid, "content": content})
    sys.exit(0)

# 沒有 tool_calls：content 就是答案，寫 $AOS_WS/out/<題名>、題目 cur/ → done/
with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
    name = f.read().strip()
content = said.get("content") or ""
if not content.endswith("\n"):
    content += "\n"
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
tmp = os.path.join(ws, "out", "." + name)         # N-05：先寫 . 開頭的暫存檔再改名
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", name))
shutil.move(os.path.join(ws, "cur", name), os.path.join(ws, "done", name))
