# brain.py - think 格：從 $AOS_STACK/queue/ 認領一則、把 tools.json 登記的工具（aos-tools ls --json）組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
# 10-30（eca 第 8 步）：agent-dan 搬到 queue 的版本（P-11 的 10-30 改口、P-42）——題目不再從 $AOS_WS/new/ 拿，
# 而是 aos-post claim（$AOS_STACK/queue/，N-16 有順序的信箱；一封信的 body＝一則 {"role": "user", "content": 字串}）。
# 認領的順序同 lib/agent/queue（Q-1）：cur/ 有沒答完的先接著做，否則 aos-post claim 一封 → body 接進 history → 信號寫進 current.txt。
# 壞信（aos-post check 不過、body 不是 user 的非空字串）＝aos-post finish 丟掉、認領下一封（Q-4、衝突 5）；都沒信＝退 10（queue 空，loop 收工）。
import json, os, subprocess, sys, urllib.error, urllib.request


def die(code, reason):
    print("agent-dan-q: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
box = os.path.join(stack, "queue")


def post(args):
    """叫 aos-post（PATH 上要有，proto8/impls/aos-post/bin）；stderr 照樣往上（它自己說原因）。"""
    try:
        return subprocess.run(["aos-post"] + args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("PostFailed", "aos-post 起不來：%s" % e)


def cur():
    try:
        return sorted(n for n in os.listdir(os.path.join(box, "cur")) if not n.startswith("."))   # . 開頭不算信（N-05）
    except (FileNotFoundError, NotADirectoryError):
        return []


def content_of(sig):
    """好信回 content；壞信回 None（不是這格的錯，不寫 stderr）。"""
    try:
        r = subprocess.run(["aos-post", "check", box, sig], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, text=True)
        body = json.loads(r.stdout).get("body") if r.returncode == 0 else None
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(body, dict) and body.get("role") == "user" and isinstance(body.get("content"), str) \
            and body["content"].strip():
        return body["content"]
    return None


while True:
    names = cur()
    if names:
        name = names[0]
    else:
        r = post(["claim", box])
        if r.returncode == 10:
            sys.exit(10)                            # queue 空（idle 看過有信、被撤回了或全是壞信）：正常停
        if r.returncode != 0:
            die("PostFailed", "aos-post claim 退 %d" % r.returncode)
        name = r.stdout.strip()
    question = content_of(name)
    if question is not None:
        break
    post(["finish", box, name])                     # 壞信照 N-16 丟掉、不通知寄信人
tmp = os.path.join(stack, ".current.txt")       # N-05：先寫 . 開頭的暫存檔再改名
with open(tmp, "w", encoding="utf-8") as f:
    f.write(name + "\n")
os.replace(tmp, os.path.join(stack, "current.txt"))

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

# tools：工具清單來自 tools.json（aos-tools ls --json；沒有 tools.json＝沒有工具），說明取工具定義的 description／parameters（其他 key 忽略）
# aos-tools 起不來、退非 0（例：登記了但壞掉的工具）＝自己這層的錯：停、人修好再跑（P-20）；aos-tools 的 stderr 不吞，它自己說哪個工具壞
try:
    r = subprocess.run(["aos-tools", "ls", "--json"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
except OSError as e:
    die("ToolsBad", "aos-tools 起不來：%s" % e)
if r.returncode != 0:
    die("ToolsBad", "aos-tools ls 退 %d" % r.returncode)
tools = []
for t in json.loads(r.stdout):
    function = {"name": t["name"]}
    function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in t["tooldef"]})
    tools.append({"type": "function", "function": function})

system = []
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]   # 每次從檔讀，不存進 history


def fake():
    last = history[-1]
    if last.get("role") == "user" and any(t["function"]["name"] == "clock" for t in tools):
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_fake_1", "type": "function",
                                "function": {"name": "clock", "arguments": "{}"}}]}
    content = "FAKE ANSWER to: " + question.rstrip("\n")
    if last.get("role") == "tool":
        content += "（clock said: %s）" % (last.get("content") or "").rstrip("\n")
    return {"role": "assistant", "content": content}


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
    report, usage = os.environ.get("AOS_KERNEL_REPORT"), json.loads(raw).get("usage")
    if report and isinstance(usage, dict):           # 經 LLM kernel 跑時把 API 回的 usage 交給它（P-23 註；不寫＝kernel 只算次數）
        tmp = os.path.join(os.path.dirname(report), "." + os.path.basename(report))   # N-05：先寫暫存再改名
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(usage, f)
        os.replace(tmp, report)
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
