# act.py - act 格：照腦的決定動手——有 tool_calls 就逐個 aos-tools call <名>、結果接回 history；沒有就把 content 寫成答案（照抄 agent-dan，只改錯誤訊息開頭的名字）
# 跟 agent-dan 差一條（10-24 遷移：tools/ 改掛 proto8/lib/base 的 ls、read、write、edit、bash）：工具一律 `AOS_WS=<要改的資料夾> aos-tools call <名>`（aos-exec 沒給 --ws＝用 $AOS_WS）——庫的工具只碰 $AOS_WS，這隻要改的程式在
#   $AOS_STACK/pyfix_dir.txt 寫的資料夾（pyfix 開子 agent 前寫的一行絕對路徑；11-01 起取代環境變數），自己的 $AOS_WS 是收題交答案的小格；
#   沒有那個檔或不是資料夾＝DirMissing 停下。
# 工具的介面：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的 stack＝$AOS_STACK/<名>/（P-17）。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑（只補沒回的）。
# 叫工具出的問題回給腦、不停（10-24 起，同原本的 agent-pip，demo 11-04 刪了）：工具退非 0（stdout 照收、尾巴加結束碼）、叫了沒有的工具、arguments 不是 JSON，
# 都接成一則 tool 訊息讓腦自己決定（停下的話重跑會再叫同一個、永遠卡住）；工具的 stderr 不讀（C-52、C-53）。
# 只有自己這層的錯（環境壞了：沒 stack、history 壞、aos-tools 起不來）才停：stderr 一行、退 1、history 不接（P-20）。
import json, os, shutil, signal, subprocess, sys

if "--help" in sys.argv[1:]:                    # --help：英文說明印 stdout、退 0（stdio-unify R3）
    print("usage: act.py   (the act cell of pyfix's sub-agent; run by its fsm.json)\n"
          "Run the tool_calls of the last assistant message in $AOS_STACK/history.jsonl, append one tool message each.\n"
          "On error: \"pyfix-agent: error: CODE reason\" on stderr, exit 1.")
    sys.exit(0)
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）


def die(code, reason):
    print("pyfix-agent: error: %s %s" % (code, reason), file=sys.stderr)
    sys.exit(1)


stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
history_path = os.path.join(stack, "history.jsonl")
history = []
try:
    with open(history_path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.strip():
                try:
                    history.append(json.loads(line))
                except ValueError as e:
                    die("HistoryBad", "history.jsonl line %d is not JSON: %s" % (n, e))
except FileNotFoundError:
    pass
last = max((i for i, m in enumerate(history) if isinstance(m, dict) and m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "no assistant message in history.jsonl")
said = history[last]


def append(message):
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


calls = said.get("tool_calls") or []
if calls:
    try:
        with open(os.path.join(stack, "pyfix_dir.txt"), encoding="utf-8") as f:
            code_dir = f.read().strip()
    except OSError:
        code_dir = ""
    if not code_dir or not os.path.isdir(code_dir):
        die("DirMissing", "$AOS_STACK/pyfix_dir.txt is missing or does not name a directory (where the code to fix is)")
    answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
    try:                                # 能叫的＝tools.json 登記的（aos-tools ls --json）；失敗＝自己這層的錯
        r = subprocess.run(["aos-tools", "ls", "--json"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("ToolFailed", "aos-tools failed to start: %s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls exited %d" % r.returncode)
    tools = [t["name"] for t in json.loads(r.stdout)]
    for call in calls:
        try:
            cid, name, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
        except (KeyError, TypeError):
            die("HistoryBad", "a tool call has no id or function.name: %s" % json.dumps(call, ensure_ascii=False))
        if cid in answered:
            continue
        if name not in tools:           # 名字只認 tools.json 登記過的（也擋掉 ../ 之類）
            append({"role": "tool", "tool_call_id": cid,
                    "content": "act: ToolUnknown %s (available: %s)\n" % (name, ", ".join(tools))})
            continue
        try:
            if not isinstance(arguments, str):
                raise ValueError("arguments is not a string")
            json.loads(arguments)
        except ValueError as e:
            append({"role": "tool", "tool_call_id": cid, "content": "act: ArgumentsBad %s: %s\n" % (name, e)})
            continue
        env = dict(os.environ, AOS_STACK=os.path.join(stack, "tools", name) + "/", AOS_WS=os.path.abspath(code_dir))   # 工作區＝pyfix_dir.txt 的資料夾（aos-exec 沒給 --ws 就用 $AOS_WS）
        try:
            r = subprocess.run(["aos-tools", "call", name], input=arguments, stdout=subprocess.PIPE,
                               text=True, env=env)      # stderr 不吞：工具自己的錯原樣往上
        except OSError as e:
            die("ToolFailed", "%s failed to start: %s" % (name, e))
        content = r.stdout
        if r.returncode != 0:           # 回給腦、不停；人在 stderr 看得到
            print("pyfix-agent: warning: tool %s exited %d (returned to the brain)" % (name, r.returncode), file=sys.stderr)   # 提醒行（stdio-unify R1）
            content += "%s(tool %s exited %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, r.returncode)
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
