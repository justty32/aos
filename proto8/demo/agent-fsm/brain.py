# brain.py [--system FILE] [--tools FILE] - think 格：帶 $AOS_STACK/history.jsonl（加 system、tools）問腦，回覆一則 assistant 接進 history。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝腦要叫工具（有 tool_calls → act）；10＝腦給了最後答案、沒事做了（→ idle）。
#   history 最後一則不是 user／tool（上一題已答完、或人改了 history）＝沒事做，不問腦、退 10（自保）。
# --system FILE：讀成一則 system 放最前面、不存進 history（P-41）；沒給＝沒有 system。
# --tools FILE：aos-tools 登記檔（預設範本裡的 tools.json；沒有那份＝不給工具）；腦看到的工具名＝登記名。相對路徑從範本資料夾（AOS_CD）算。
# 腦（P-23）：AOS_BRAIN_URL 沒設＝假腦（有工具就先叫第一個、再答一句，不碰網路）；有設＝問 OpenAI 相容的 {url}/chat/completions，
#   AOS_BRAIN_MODEL（範本 .env）、AOS_BRAIN_KEY（有才帶 Bearer）；只留 role、content、tool_calls。
# 錯：stderr 一行「agent-fsm: 代號 原因」、退 1、history 不接（P-20）。照舊的 agent-eve 的 brain.py 改（11-04 隨 proto8/tests 刪了）（拿掉工作區題目認領與 current.txt）。
import json, os, subprocess, sys, urllib.error, urllib.request


def die(code, reason):
    print("agent-fsm: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def flags(argv, known):
    out, i = {}, 0
    while i < len(argv):
        if argv[i] not in known or i + 1 >= len(argv) or not argv[i + 1]:
            die("ArgumentsBad", "用法：brain.py [--system FILE] [--tools FILE]（看不懂 %s）" % argv[i])
        out[argv[i]] = argv[i + 1]
        i += 2
    return out


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


opts = flags(sys.argv[1:], ("--system", "--tools"))
system_file = here(opts["--system"]) if "--system" in opts else None
if system_file and not os.path.isfile(system_file):
    die("SystemMissing", "system 檔不在：%s" % system_file)
tools_file = here(opts.get("--tools", "tools.json"))
if "--tools" not in opts and os.path.isfile(os.path.join(os.environ.get("AOS_STACK") or "", "tools.json")):
    tools_file = os.path.join(os.environ["AOS_STACK"], "tools.json")   # 子介面 tools：stack 有副本就用它（aos-agent tools，11-04）
if "--tools" in opts and not os.path.isfile(tools_file):
    die("ToolsMissing", "工具登記檔不在：%s" % tools_file)
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")

# 對話：一行一則 OpenAI message（C-46、P-41），只附加
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                if not isinstance(m, dict):
                    die("HistoryBad", "history.jsonl 第 %d 行不是 JSON 物件" % n)
                history.append(m)
except FileNotFoundError:
    pass
except OSError as e:
    die("HistoryBad", "讀不了 history.jsonl：%s" % e)
if not history or history[-1].get("role") not in ("user", "tool"):
    sys.exit(10)                                 # 沒有要答的：回 idle 等信

# tools：登記檔裡的工具（aos-tools ls --json；登記檔不在＝沒有工具），說明取工具定義的 description／parameters
tools = []
if os.path.isfile(tools_file):
    try:
        r = subprocess.run(["aos-tools", "--file", tools_file, "ls", "--json"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, text=True)            # stderr 不吞：aos-tools 自己說哪個工具壞
    except OSError as e:
        die("ToolsBad", "aos-tools 起不來：%s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls 退 %d" % r.returncode)
    for t in json.loads(r.stdout):
        function = {"name": t["name"]}
        function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in t["tooldef"]})
        tools.append({"type": "function", "function": function})

system = []
if system_file:
    try:
        with open(system_file, encoding="utf-8") as f:
            system = [{"role": "system", "content": f.read()}]           # 每次從檔讀，不存進 history
    except OSError as e:
        die("SystemMissing", "讀不了 %s：%s" % (system_file, e))


def fake():
    """假腦：最後一則是 user、有工具＝先叫第一個工具；否則答一句（帶上最後那則 user 與工具的結果）。"""
    last = history[-1]
    if last.get("role") == "user" and tools:
        return {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call_fake_%d" % len(history), "type": "function",
                                "function": {"name": tools[0]["function"]["name"], "arguments": "{}"}}]}
    question = next((m.get("content") or "" for m in reversed(history) if m.get("role") == "user"), "")
    content = "FAKE ANSWER to: " + question.rstrip("\n")
    if last.get("role") == "tool":
        content += "（tool said: %s）" % (last.get("content") or "").rstrip("\n")
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
        die("BrainFailed", "HTTP %d：%s" % (e.code, detail))
    except (urllib.error.URLError, OSError) as e:     # 連不上、逾時（TimeoutError 是 OSError）
        die("BrainFailed", "%s 連不上或逾時：%s" % (url, getattr(e, "reason", e)))
    try:
        reply = json.loads(raw)
        message = reply["choices"][0]["message"]
    except (ValueError, KeyError, IndexError, TypeError) as e:
        die("ReplyBad", "回覆不是 OpenAI 的形狀（%s: %s）" % (type(e).__name__, e))
    report, usage = os.environ.get("AOS_KERNEL_REPORT"), reply.get("usage") if isinstance(reply, dict) else None
    if report and isinstance(usage, dict):           # 經 LLM kernel 跑時把 API 回的 usage 交給它（P-23 註）
        tmp = os.path.join(os.path.dirname(report), "." + os.path.basename(report))   # N-05：先寫暫存再改名
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(usage, f)
        os.replace(tmp, report)
    if not isinstance(message, dict):
        die("ReplyBad", "choices[0].message 不是物件")
    out = {"role": "assistant", "content": message.get("content")}
    calls = message.get("tool_calls")
    if calls:
        if not isinstance(calls, list) or not all(isinstance(c, dict) for c in calls):
            die("ReplyBad", "tool_calls 不是物件的陣列")
        out["tool_calls"] = [{k: c[k] for k in ("id", "type", "function") if k in c} for c in calls]
    return out                                       # 只留 role、content、tool_calls（模型想的內容不收，P-23）


# 子介面 llm（11-04）：stack 有副本 llm.json 就用它的鍵蓋過 AOS_BRAIN_*（aos-agent llm set 寫的；每格重讀＝下一題生效）
try:
    with open(os.path.join(stack, "llm.json"), encoding="utf-8") as f:
        brain_copy = json.load(f)
except FileNotFoundError:
    brain_copy = {}
except (OSError, ValueError) as e:
    die("CfgBad", "llm.json 讀不懂：%s" % e)
if not isinstance(brain_copy, dict):
    die("CfgBad", "llm.json 要是一層物件")
for k, var in (("url", "AOS_BRAIN_URL"), ("model", "AOS_BRAIN_MODEL"), ("key", "AOS_BRAIN_KEY")):
    if isinstance(brain_copy.get(k), str):
        os.environ[var] = brain_copy[k]
url = os.environ.get("AOS_BRAIN_URL")
said = fake() if not url else ask(url)
try:
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(said, ensure_ascii=False) + "\n")
except OSError as e:
    die("WriteFailed", "接不進 history.jsonl：%s" % e)
sys.exit(0 if said.get("tool_calls") else 10)
