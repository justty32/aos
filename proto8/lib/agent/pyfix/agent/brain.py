# brain.py - think 格：認領題目、把 tools.json 登記的工具（aos-tools ls --json）組成 tools、帶 $AOS_STACK/history.jsonl 問腦，回覆一行接進 history（照抄 agent-dan，只改錯誤訊息開頭的名字）
# 問腦＝寄請求給 llm kernel、同步等回信：`aos-llm ask`（stdin＝{"request": {messages, tools}}；用 kernel 的預設代號，假腦＝kernel 的 fake；
#   11-04 晚 think-as-function 03 § 3：pyfix 是工具形、一次跑完，同步就好）。$AOS_KERNEL 沒設＝aos-llm 報 KernelMissing。
# 失敗時 history 不接任何東西、退 1（P-20）：BrainFailed（aos-llm 退非 0，它自己的 stderr 在上面）、ReplyBad。
import json, os, subprocess, sys


def die(code, reason):
    print("pyfix-agent: %s %s" % (code, reason), file=sys.stderr)
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


def ask():
    request = {"messages": system + history}
    if tools:
        request["tools"] = tools
    try:
        r = subprocess.run(["aos-llm", "ask"], input=json.dumps({"request": request}, ensure_ascii=False),
                           stdout=subprocess.PIPE, text=True)      # stderr 不吞：aos-llm 自己說原因
    except OSError as e:
        die("BrainFailed", "aos-llm 起不來（要在 PATH 上）：%s" % e)
    if r.returncode != 0:
        die("BrainFailed", "aos-llm ask 退 %d" % r.returncode)
    try:
        message = json.loads(r.stdout)
    except ValueError as e:
        die("ReplyBad", "aos-llm ask 印的不是 JSON：%s" % e)
    if not isinstance(message, dict):
        die("ReplyBad", "回信的 message 不是物件")
    return message                                   # kernel 的 endpoint 函數已只留 role、content、tool_calls（P-23）


append(ask())
