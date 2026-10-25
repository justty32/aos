# brain.py - think 格（抄 agent-dan）：認領題目、把 tools/*/tool.json 組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history
# 沒設 AOS_BRAIN_URL＝假腦（第四輪：固定回四行「承接：2」「像柚葉：2」「文筆：2」「理由：假腦」，照 system.v2.txt 的格式；
# 測試要換回覆時設 GALTXT_FAKE_GRADE＝整段回覆（\n 換行；只有假腦讀））；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
# 跟範本不同的兩處：fake() 改寫；評審沒有 tools/，tools 陣列是空的、不帶；問真腦時把 API 回的 usage 多記一行到 $AOS_STACK/usage.jsonl（給實測對照用，OpenAI 的欄位名照留）。
import datetime, json, os, sys, urllib.error, urllib.request


def die(code, reason):
    print("judge: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")


def ls(d):
    try:
        return sorted(n for n in os.listdir(os.path.join(ws, d)) if not n.startswith("."))   # . 開頭＝別人寫到一半的暫存檔（N-05），不撿
    except FileNotFoundError:
        return []


# 認領題目：cur/ 有上次認領沒做完的先接著做，沒有就把 new/ 第一題搬到 cur/
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

system = []
if os.path.exists("system.txt"):
    with open("system.txt", encoding="utf-8") as f:
        system = [{"role": "system", "content": f.read()}]   # 每次從檔讀，不存進 history

def fake():
    """假腦：三項固定給 2 分（離線測試用；兩份同分時 pick 的平手規則才測得到）。"""
    reply = os.environ.get("GALTXT_FAKE_GRADE")
    return {"role": "assistant", "content": reply.replace("\\n", "\n") if reply is not None else "承接：2\n像柚葉：2\n文筆：2\n理由：假腦"}


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
    if isinstance(usage, dict):                      # 實測用：每次回覆一行，OpenAI usage 原名照留
        at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with open(os.path.join(stack, "usage.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(dict({"recorded_at": at}, **usage), ensure_ascii=False) + "\n")
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
