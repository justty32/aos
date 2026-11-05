# act.py [--tools FILE] - act 格：照 history 最後一則 assistant 的 tool_calls 逐個（依序）aos-tools call <名>，每個結果接一則 tool 進 history。
# 結束碼（fsm.json 照碼分岔，N-36）：全部跑完退 0（→ think：帶工具結果再問腦）；最後一則 assistant 沒有 tool_calls＝腦給了最後答案、沒事做，退 10（→ idle）。
#   「要不要叫工具」11-04 晚從 think 搬到這裡判（think 只組請求，thinking 2026-11-04 think-as-function 03 § 1）。
# 工具的介面（P-41）：arguments（JSON 字串）原樣從 stdin 進、stdout 整段是結果；工具的小格＝$AOS_STACK/tools/<名>/（P-17）、工作區＝$AOS_WS。
# 中途失敗重跑時，已經有 tool 訊息的 id 不再跑（只補沒回的）。
# 叫工具出的問題回給腦、不停（P-41 10-24 代定）：工具退非 0（stdout 照收、尾巴加結束碼）、叫了沒登記的工具、arguments 不是 JSON。
# 只有自己這層的錯才停：stderr 一行「agent-fsm: 代號 原因」、退 1、history 不接（P-20）——沒 stack、history 壞、
#   history 裡沒有 assistant、aos-tools 起不來。
# --tools FILE：aos-tools 登記檔（預設範本裡的 tools.json；沒有那份＝沒有工具）。相對路徑從範本資料夾（AOS_CD）算。
#   沒給 --tools 時，$AOS_STACK/tools.json 在＝疊上這隻的覆蓋層（aos-tools --overlay；aos-agent tools add／rm 寫的，只存差異，11-05）。
# 照舊的 agent-eve 的 act.py 改（拿掉 out/、done/、current.txt；agent-eve 11-04 隨 proto8/tests 刪了）。
import json, os, subprocess, sys


def die(code, reason):
    print("agent-fsm: %s %s" % (code, str(reason).replace("\n", " ")), file=sys.stderr)
    sys.exit(1)


def flags(argv, known):
    out, i = {}, 0
    while i < len(argv):
        if argv[i] not in known or i + 1 >= len(argv) or not argv[i + 1]:
            die("ArgumentsBad", "用法：act.py [--tools FILE]（看不懂 %s）" % argv[i])
        out[argv[i]] = argv[i + 1]
        i += 2
    return out


opts = flags(sys.argv[1:], ("--tools",))
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "沒設定 AOS_STACK")
tools_file = os.path.join(os.environ.get("AOS_CD") or ".", opts.get("--tools", "tools.json"))
if "--tools" in opts and not os.path.isfile(tools_file):
    die("ToolsMissing", "工具登記檔不在：%s" % tools_file)
overlay = os.path.join(stack, "tools.json")         # 子介面 tools 的覆蓋層（aos-agent tools，11-05 起只存差異）
overlay = overlay if "--tools" not in opts and os.path.isfile(overlay) else None
TOOLS = ["aos-tools", "--file", tools_file] + (["--overlay", overlay] if overlay else [])
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
last = max((i for i, m in enumerate(history) if m.get("role") == "assistant"), default=None)
if last is None:
    die("HistoryBad", "history.jsonl 裡沒有 assistant 的訊息")
calls = history[last].get("tool_calls")
if not calls:
    sys.exit(10)                                 # 最後答案：沒有工具要叫，回 idle 等信
if not isinstance(calls, list):
    die("HistoryBad", "最後一則 assistant 的 tool_calls 不是陣列")


def append(message):
    try:
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "接不進 history.jsonl：%s" % e)


registered = []
if os.path.isfile(tools_file) or overlay:        # 能叫的＝登記檔（疊覆蓋層）裡的（aos-tools ls --json）；失敗＝自己這層的錯
    try:
        r = subprocess.run(TOOLS + ["ls", "--json"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, text=True)
    except OSError as e:
        die("ToolFailed", "aos-tools 起不來：%s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls 退 %d" % r.returncode)
    registered = [t["name"] for t in json.loads(r.stdout)]
answered = {m.get("tool_call_id") for m in history[last + 1:] if m.get("role") == "tool"}
for call in calls:
    try:
        cid, name, arguments = call["id"], call["function"]["name"], call["function"].get("arguments")
    except (KeyError, TypeError):
        die("HistoryBad", "tool_calls 裡有一個沒有 id 或 function.name：%s" % json.dumps(call, ensure_ascii=False))
    if cid in answered:
        continue
    if name not in registered:                   # 名字只認登記過的（也擋掉 ../ 之類）
        append({"role": "tool", "tool_call_id": cid,
                "content": "act: ToolUnknown %s（能叫的：%s）\n" % (name, "、".join(registered))})
        continue
    try:
        if not isinstance(arguments, str):
            raise ValueError("arguments 不是字串")
        json.loads(arguments)
    except ValueError as e:
        append({"role": "tool", "tool_call_id": cid, "content": "act: ArgumentsBad %s：%s\n" % (name, e)})
        continue
    env = dict(os.environ, AOS_STACK=os.path.join(stack, "tools", name) + "/")
    try:
        r = subprocess.run(TOOLS + ["call", name], input=arguments,
                           stdout=subprocess.PIPE, text=True, env=env)   # stderr 不吞：工具自己的錯原樣往上
    except OSError as e:
        die("ToolFailed", "aos-tools 起不來：%s" % e)
    content = r.stdout
    if r.returncode != 0:                        # 回給腦、不停；人在 stderr 看得到
        print("agent-fsm: ToolFailed %s 結束碼 %d（回給腦）" % (name, r.returncode), file=sys.stderr)
        content += "%s(工具 %s 結束碼 %d)\n" % ("" if content.endswith("\n") or not content else "\n", name, r.returncode)
    append({"role": "tool", "tool_call_id": cid, "content": content})
sys.exit(0)
