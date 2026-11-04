# brain.py [--system FILE] [--tools FILE] - think 格：帶 $AOS_STACK/history.jsonl（加 system、tools）組一份問腦的請求，寫 $AOS_STACK/think/request.json；不碰網路。
# 寄出去、收回信是下一格 wait（wait.py：aos-llm send／recv，經 $AOS_KERNEL 的 llm kernel；thinking 2026-11-04 think-as-function 03 § 1）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝請求寫好了（→ wait）；10＝history 最後一則不是 user／tool（上一題已答完、或人改了 history）＝沒事做（→ idle）。
# 請求＝llm kernel 請求信的 body：{"endpoint"?: 代號, "request": {"messages", "tools"?, "model"?}}。
#   endpoint／model 來自範本的 llm.json（AOS_CD）疊 $AOS_STACK/llm.json（副本，aos-agent llm set 寫的；有的鍵蓋過定義），每格重讀＝下一題生效；
#   都沒寫＝不放（kernel 用它自己的預設代號）。其他鍵不看（C-48）。
# 寫新請求時順手刪 $AOS_STACK/think/pending.txt（上一封的名字）：新請求取代舊的，wait 會重寄。
# --system FILE：讀成一則 system 放最前面、不存進 history（P-41）；沒給＝沒有 system。
# --tools FILE：aos-tools 登記檔（預設範本裡的 tools.json；沒有那份＝不給工具）；腦看到的工具名＝登記名。相對路徑從範本資料夾（AOS_CD）算。
# 錯：stderr 一行「agent-fsm: 代號 原因」、退 1（P-20）。照舊的 agent-eve 的 brain.py 改（11-04 隨 proto8/tests 刪了）（拿掉工作區題目認領與 current.txt）。
import json, os, subprocess, sys


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


def read_cfg(path):
    """llm.json：一層物件；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        die("CfgBad", "%s 讀不懂：%s" % (path, e))
    if not isinstance(d, dict):
        die("CfgBad", "%s 要是一層物件" % path)
    return d


cfg = read_cfg(here("llm.json"))
cfg.update(read_cfg(os.path.join(stack, "llm.json")))   # 副本有的鍵蓋過定義（aos-agent llm set，每格重讀）
request = {"messages": system + history}
if tools:
    request["tools"] = tools
body = {"request": request}
for k, into in (("endpoint", body), ("model", request)):
    if k in cfg:
        if not isinstance(cfg[k], str) or not cfg[k]:
            die("CfgBad", "llm.json 的 %s 要是非空字串" % k)
        into[k] = cfg[k]

think = os.path.join(stack, "think")
path = os.path.join(think, "request.json")
tmp = os.path.join(think, ".request.json.tmp")                # N-05：先寫暫存再改名
try:
    os.makedirs(think, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    try:
        os.remove(os.path.join(think, "pending.txt"))         # 新請求取代上一封（wait 會重寄）
    except FileNotFoundError:
        pass
except OSError as e:
    die("WriteFailed", "寫不了 %s：%s" % (path, e))
sys.exit(0)
