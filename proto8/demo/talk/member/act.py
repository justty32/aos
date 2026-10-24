# act.py - act 格（照抄 agent-dan，加一件）：照腦的決定動手——有 tool_calls 就逐個 aos-exec tools/<名>、結果接回 history；沒有就把 content 寫成答案
#   多的：題目是一封 expect_reply 的信、而且處理這封時還沒寄過信給寄件人＝把答案當回信，經 tools/send_message 寄回去（expect_reply false，不會再被自動回）
# 工具的介面：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的 stack＝$AOS_STACK/<名>/（P-17）。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑（只補沒回的）。任何錯：stderr 一行、退 1、history 不接（P-20）。
import json, os, shutil, subprocess, sys


def die(code, reason):
    print("talk-member: %s %s" % (code, reason), file=sys.stderr)
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
            die("ToolUnknown", name)
        if not isinstance(arguments, str):
            die("ArgumentsBad", "%s：arguments 不是字串" % name)
        try:
            json.loads(arguments)
        except ValueError as e:
            die("ArgumentsBad", "%s：%s" % (name, e))
        env = dict(os.environ, AOS_STACK=os.path.join(stack, name) + "/")
        try:
            r = subprocess.run(["aos-exec", "tools/" + name], input=arguments, stdout=subprocess.PIPE,
                               text=True, env=env)      # stderr 不吞：工具自己的錯原樣往上
        except OSError as e:
            die("ToolFailed", "%s 起不來：%s" % (name, e))
        if r.returncode != 0:
            die("ToolFailed", "%s 結束碼 %d" % (name, r.returncode))
        append({"role": "tool", "tool_call_id": cid, "content": r.stdout})
    sys.exit(0)

# 沒有 tool_calls：content 就是答案，寫 $AOS_WS/out/<題名>、題目 cur/ → done/
with open(os.path.join(stack, "current.txt"), encoding="utf-8") as f:
    name = f.read().strip()
content = said.get("content") or ""
if not content.endswith("\n"):
    content += "\n"


def auto_reply():
    # 回信要寄的時候回一句寄出結果（寫在 out/ 的答案後面）；不用寄回 None
    try:
        with open(os.path.join(ws, "cur", name), encoding="utf-8") as f:
            letter = json.load(f)
    except (OSError, ValueError):
        return None
    if not (isinstance(letter, dict) and letter.get("kind") == "letter" and letter.get("expect_reply")):
        return None
    sender, lid = letter.get("from"), letter.get("id")
    sent = os.path.join(ws, "sent")
    for n in (os.listdir(sent) if os.path.isdir(sent) else []):     # 處理這封時自己已經回過寄件人（或中途失敗重跑）就不再寄
        try:
            with open(os.path.join(sent, n), encoding="utf-8") as f:
                s = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(s, dict) and s.get("reply_to") == lid and s.get("to") == sender:
            return None
    subject = letter.get("subject") or ""
    arguments = json.dumps({"to": sender, "subject": subject if subject.startswith("Re: ") else "Re: " + subject,
                            "body": content, "expect_reply": False}, ensure_ascii=False)
    env = dict(os.environ, AOS_STACK=os.path.join(stack, "send_message") + "/")
    try:
        r = subprocess.run(["aos-exec", "tools/send_message"], input=arguments, stdout=subprocess.PIPE, text=True, env=env)
    except OSError as e:
        die("ToolFailed", "send_message 起不來：%s" % e)
    if r.returncode != 0:
        die("ToolFailed", "send_message 結束碼 %d（自動回信給 %s）" % (r.returncode, sender))
    return r.stdout


note = auto_reply()
if note:
    content += "\n〔自動回信〕" + note
os.makedirs(os.path.join(ws, "out"), exist_ok=True)
os.makedirs(os.path.join(ws, "done"), exist_ok=True)
out_name = name[:-5] + ".txt" if name.endswith(".json") else name   # 信 <id>.json 的答案是純文字 <id>.txt
tmp = os.path.join(ws, "out", "." + out_name)     # N-05：先寫 . 開頭的暫存檔再改名
with open(tmp, "w", encoding="utf-8") as f:
    f.write(content)
os.replace(tmp, os.path.join(ws, "out", out_name))
shutil.move(os.path.join(ws, "cur", name), os.path.join(ws, "done", name))
