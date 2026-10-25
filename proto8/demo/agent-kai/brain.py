# brain.py - think 格（agent-kai：照抄 agent-dan，只改「送給腦的是什麼」）：認領題目、題目接進 $AOS_STACK/history.jsonl，
# 但問腦時不送整份 history，而是按這題的意圖組一份「工作 context」：
#   system.txt ＋ 先前對話的目錄（一題一行）＋〔有記憶庫就附相關幾筆〕＋ 挑出來的舊題（只有問題與結論，過程不帶）＋ 這題到目前為止的完整訊息。
# 挑哪幾題由程式照字面決定（上一題、指代詞→上兩題、「第 N 題」、字面重疊最多的兩題）；不夠時腦自己用 recall 工具找、展開（漸進展開）。
# 整份 history 還很短（粗估 ≤ KAI_FULL_UNDER，預設 1500 token）時直接全送，跟 agent-dan 一樣。
# history.jsonl 照舊是完整紀錄、只附加；每次組了什麼記一行到 $AOS_STACK/context.jsonl（可追查）。
# 沒設 AOS_BRAIN_URL＝假腦；有設就問 OpenAI 相容的 {url}/chat/completions。失敗時 history 不接任何東西、退 1（P-20）。
import datetime, json, os, subprocess, sys, urllib.error, urllib.request

sys.path.insert(0, os.path.join("tools", "recall"))
import turns  # noqa: E402


def die(code, reason):
    print("agent-kai: %s %s" % (code, reason), file=sys.stderr)
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

# 對話：一行一則 OpenAI message（C-46），只附加
history_path = os.path.join(stack, "history.jsonl")
try:
    history = turns.load(history_path)
except turns.HistoryBad as e:
    die("HistoryBad", str(e))

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
        system_text = f.read()                     # 每次從檔讀，不存進 history


def recall_memory(q):
    """有 tools/memory（例：連到 agent-meg 的記憶庫工具）而且記憶庫在，就用它的 search 找跟這題有關的幾筆；沒有就空字串。"""
    heap = os.environ.get("AOS_HEAP") or os.path.join(ws, ".heap")
    if not os.path.isfile(os.path.join("tools", "memory", "tool.json")) or not os.path.isdir(heap):
        return ""
    env = dict(os.environ, AOS_STACK=os.path.join(stack, "memory") + "/", AOS_HEAP=heap)
    try:
        r = subprocess.run(["aos-exec", "tools/memory"], input=json.dumps({"op": "search", "query": q, "limit": 3}),
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=env, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    out = r.stdout.strip()
    if r.returncode != 0 or not out or out.startswith("沒有找到") or out.startswith("錯誤"):
        return ""
    return "## 記憶庫裡跟這題可能有關的（自動找的；不夠用 memory 工具）\n" + out


# 工作 context：按意圖組，不是整份 history
done, current = turns.split(history)
picked = turns.choose(question, done)
memory = recall_memory(question)
parts = [p for p in (system_text.rstrip("\n"), turns.directory(done), memory) if p]
if done:
    parts.append("（下面只附了跟這題有關的幾題完整問答（只有問題與結論）；其他舊題只有目錄那一行，"
                 "要細節或當時工具的原始輸出就用 recall 工具。）")
system = [{"role": "system", "content": "\n\n".join(parts)}] if parts else []
opened = [m for no, _ in picked for m in turns.opened(done[no - 1])]
keep = ("role", "content", "tool_calls", "tool_call_id")
work = opened + [{k: m[k] for k in keep if k in m} for m in current]
full_text = "\n\n".join(p for p in (system_text.rstrip("\n"), memory) if p)
full_system = [{"role": "system", "content": full_text}] if full_text else []
full = [{k: m[k] for k in keep if k in m} for m in history]
try:
    full_under = int(os.environ.get("KAI_FULL_UNDER") or 1500)
except ValueError:
    full_under = 1500
mode = "intent"
if turns.estimate(full_system + full) <= full_under:   # 整份還很短：直接全送（不會比挑過的貴，也不會漏）
    system, work, picked, mode = full_system, full, [], "full"
with open(os.path.join(stack, "context.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
                        "question": name, "mode": mode, "counter_turns": len(done), "picked": [[no, why] for no, why in picked],
                        "memory": bool(memory), "counter_history_messages": len(history), "counter_sent_messages": len(system + work),
                        "est_tokens": turns.estimate(system + work), "est_tokens_full": turns.estimate(full_system + full)},
                       ensure_ascii=False) + "\n")


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
    body = {"model": os.environ.get("AOS_BRAIN_MODEL") or "default", "messages": system + work}
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
