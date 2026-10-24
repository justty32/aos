# brain.py - think 格（照抄 agent-dan，加兩件）：認領題目、把 tools/*/tool.json 組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
#   多的 1：題目是信（new/<id>.json，kind＝letter）就翻成一段「[來信] …」給腦看
#   多的 2：system 訊息＝system.txt＋名冊（$AOS_ROSTER）：我是誰、角色、還有誰、有哪些群組
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
import json, os, sys, urllib.error, urllib.request


def die(code, reason):
    print("talk-member: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, d)) if not n.startswith("."))   # . 開頭＝別人寫到一半的暫存檔（N-05），不撿
    except FileNotFoundError:
        return []


# 認領題目（同 bob）：cur/ 有上次認領沒做完的先接著做，沒有就把 new/ 第一題搬到 cur/
names = ls("cur")
if not names:
    names = ls("new")
    if not names:
        die("QuestionMissing", "new/ 是空的")
    os.makedirs(os.path.join(ws, "cur"), exist_ok=True)
    os.replace(os.path.join(ws, "new", names[0]), os.path.join(ws, "cur", names[0]))
name = names[0]
tmp = os.path.join(stack, ".current.txt")       # N-05：先寫 . 開頭的暫存檔再改名
with open(tmp, "w", encoding="utf-8") as f:
    f.write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))
with open(os.path.join(ws, "cur", name), encoding="utf-8") as f:
    question = f.read()
letter = None
if name.endswith(".json"):
    try:
        letter = json.loads(question)
    except ValueError:
        letter = None
    if not (isinstance(letter, dict) and letter.get("kind") == "letter"):
        letter = None
if letter:
    question = "[來信] 寄件人：%s%s\n對話串：%s（第 %s 手）\n要你回答：%s\n主旨：%s\n---\n%s" % (
        letter.get("from"), "（寄給群組 %s）" % letter["group"] if letter.get("group") else "",
        letter.get("thread"), letter.get("hops"),
        "是（直接用純文字回答，會自動寄回給 %s）" % letter.get("from") if letter.get("expect_reply") else "否（只是回覆或通知）",
        letter.get("subject") or "（無）", letter.get("body", ""))

# 對話：一行一則 OpenAI message（C-46），只附加
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


def append(message):
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")
    history.append(message)


# 最後一則不是 user／tool（空的、或上一題已答完）才接題目；腦失敗後重跑時不會重複接
if not history or history[-1].get("role") not in ("user", "tool"):
    append({"role": "user", "content": question})

# tools：工具名＝資料夾名，說明來自 tool.json 的 description／parameters（其他 key 忽略；讀不懂的 tool.json 當作沒有）
tools = []
for tool in (sorted(os.listdir("tools")) if os.path.isdir("tools") else []):
    try:
        with open(os.path.join("tools", tool, "tool.json"), encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError):
        continue
    if not isinstance(spec, dict):
        continue
    function = {"name": tool}
    function.update({k: spec[k] for k in ("description", "parameters") if k in spec})
    tools.append({"type": "function", "function": function})

system_text = ""
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system_text = f.read()                    # 每次從檔讀，不存進 history


def roster_text():
    # 名冊：讀不到就不加（寄信的工具自己會報錯）；我是誰＝信箱跟 $AOS_WS 同一個資料夾的那位
    path = os.environ.get("AOS_ROSTER")
    try:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
        members, base = r["members"], os.path.dirname(os.path.abspath(path))
    except (TypeError, OSError, ValueError, KeyError):
        return ""
    here = os.path.realpath(ws)
    me = next((n for n, m in members.items()
               if os.path.realpath(os.path.join(base, m.get("mailbox", ""))) == here), None)
    lines = ["", "## 團隊名冊"]
    if me:
        lines.append("你是 %s。你的角色：%s" % (me, members[me].get("role", "（沒寫）")))
    lines.append("成員：")
    for n, m in members.items():
        if n != me:
            lines.append("- %s：%s" % (n, m.get("role", "（沒寫）")))
    for g, ns in (r.get("groups") or {}).items():
        lines.append("- 群組 %s＝%s" % (g, "、".join(ns)))
    return "\n".join(lines) + "\n"


system_text += roster_text()
system = [{"role": "system", "content": system_text}] if system_text else []


def fake():
    # 假腦：不叫工具，直接答（信要回答時，act 會把這句自動寄回給寄件人）
    first = (letter.get("body", "") if letter else question).strip().splitlines()
    return {"role": "assistant", "content": "FAKE ANSWER to: " + (first[0] if first else "")}


def ask(url):
    body = {"model": os.environ.get("AOS_BRAIN_MODEL") or "default", "messages": system + history}
    if tools:
        body["tools"] = tools
    headers = {"Content-Type": "application/json"}
    if os.environ.get("AOS_BRAIN_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["AOS_BRAIN_KEY"]
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions",
                                 json.dumps(body, ensure_ascii=False).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode("utf-8", "replace")
        die("BrainFailed", ("HTTP %d：%s" % (e.code, detail)).replace("\n", " "))
    except (urllib.error.URLError, OSError) as e:     # 連不上、逾時（TimeoutError 是 OSError）
        die("BrainFailed", ("%s 連不上或逾時：%s" % (url, getattr(e, "reason", e))).replace("\n", " "))
    try:
        message = json.loads(raw)["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        die("ReplyBad", ("回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e)).replace("\n", " "))
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    out = {"role": message.get("role") or "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out                                       # 只留 role、content、tool_calls（模型想的內容不收，P-23）


url = os.environ.get("AOS_BRAIN_URL")
append(fake() if not url else ask(url))
