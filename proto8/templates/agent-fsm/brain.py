# brain.py [--system FILE] [--tools FILE] [--memory NAME] - think 格：帶 $AOS_STACK/history.jsonl（加 system、tools）組一份問腦的請求，寫 $AOS_STACK/think/request.json；不碰網路。
# 寄出去、收回信是下一格 wait（wait.py：aos-llm send／recv，經 $AOS_LLM_KERNEL〔llm kernel 的 stack〕的 llm kernel；thinking 2026-11-04 think-as-function 03 § 1）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝請求寫好了（→ wait）；10＝history 最後一則不是 user／tool（上一題已答完、或人改了 history）＝沒事做（→ idle）。
# 請求＝llm kernel 請求信的 body：{"endpoint"?: 代號, "request": {"messages", "tools"?}}（不寫 model：model 綁在 kernel 的 endpoint 包上）。
#   endpoint 來自範本的 llm.json（AOS_CD）疊 $AOS_STACK/llm.json（只放改過的鍵，aos-agent llm set 寫的；有的鍵蓋過定義），每格重讀＝下一題生效；
#   都沒寫＝不放（kernel 用它自己的預設代號）。其他鍵不看（C-48）。
# 寫新請求時順手刪 $AOS_STACK/think/pending.txt（上一封的名字）：新請求取代舊的，wait 會重寄。
# --system FILE：讀成一則 system 放最前面、不存進 history（P-41）；沒給＝沒有 system。
# --memory NAME（11-05 晚 agent-knowledge K2）：登記名 NAME 的工具（memory）叫一次 {"op": "read"}，它印的知識庫根接在 system 後面、
#   同一則 system 訊息（每格重叫＝知識庫改了下一題就看到；不存進 history）。叫的是腦之後叫的同一個工具＝腦看到的根跟它自己查的一樣。
#   工具清單（疊覆蓋層後）沒有 NAME＝不給根（這隻把 memory 拿掉了）；叫了退非 0、或 30 秒沒叫完（整群收掉）＝MemoryFailed（工具自己那行照樣在 stderr）。
# --tools FILE：aos-tools 登記檔（預設範本裡的 tools.json；沒有那份＝不給工具）；腦看到的工具名＝登記名。相對路徑從範本資料夾（AOS_CD）算。
#   沒給 --tools 時，$AOS_STACK/tools.json 在＝疊上這隻的覆蓋層（aos-tools --overlay；aos-agent tools add／rm 寫的，只存差異，11-05）。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1（P-20）。--help 印英文用法；Ctrl-C 退 130。照舊的 agent-eve 的 brain.py 改（11-04 隨 proto8/tests 刪了）（拿掉工作區題目認領與 current.txt）。
import json, os, shutil, signal, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "py"))   # py/aos_flags.py（錯誤行、提醒行的共用介面）
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(shutil.which("aos-tools") or "/")), "..", "..", "..", "py"))   # 複製出 repo 的：從 PATH 上 aos-tools 的真位置找 proto8/py
import aos_flags  # noqa: E402

HELP = """\
usage: brain.py [--system FILE] [--tools FILE] [--memory NAME]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The think cell: build the request to the brain from $AOS_STACK/history.jsonl (plus system and
tools) and write $AOS_STACK/think/request.json. Exit 0 = written (go wait); 10 = nothing to answer.
--system FILE: a system message in front; --tools FILE: the aos-tools registry;
--memory NAME: call tool NAME with {"op": "read"} and append the knowledge base root it prints
to the system message (skipped when NAME is not among the tools).
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）
MEMORY_TIMEOUT_S = 30                           # --memory 叫根的逾時（11-05 夜第二輪邊緣：原本沒逾時，memory 卡住＝think 格卡住）


def die(code, reason):
    aos_flags.die("agent-fsm", code, reason)


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


try:
    values, rest = aos_flags.parse(sys.argv[1:], {}, multi={'--system': '--system', '--tools': '--tools', '--memory': '--memory'}, help=HELP)
except aos_flags.Error as e:
    die(e.code, e)
if rest:
    die("ArgumentsBad", "unexpected argument %s (usage: brain.py [--system FILE] [--tools FILE] [--memory NAME])" % rest[0])
# 收齊重複值再取最後一個：任一次空值都照舊報錯，不讓後面的值蓋掉錯誤。
for flag, items in values.items():
    if any(not value for value in items):
        die("ArgumentsBad", "%s needs a non-empty value (usage: brain.py [--system FILE] [--tools FILE] [--memory NAME])" % flag)
opts = {flag: items[-1] for flag, items in values.items()}
system_file = here(opts["--system"]) if "--system" in opts else None
if system_file and not os.path.isfile(system_file):
    die("SystemMissing", "system file not found: %s" % system_file)
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
tools_file = here(opts.get("--tools", "tools.json"))
if "--tools" in opts and not os.path.isfile(tools_file):
    die("ToolsMissing", "tool registry not found: %s" % tools_file)
overlay = os.path.join(stack, "tools.json")         # 子介面 tools 的覆蓋層（aos-agent tools，11-05 起只存差異）
overlay = overlay if "--tools" not in opts and os.path.isfile(overlay) else None

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
                    die("HistoryBad", "history.jsonl line %d is not a JSON object" % n)
                history.append(m)
except FileNotFoundError:
    pass
except OSError as e:
    die("HistoryBad", "cannot read history.jsonl: %s" % e)
if not history or history[-1].get("role") not in ("user", "tool"):
    sys.exit(10)                                 # 沒有要答的：回 idle 等信

# tools：登記檔裡的工具（aos-tools ls --json；登記檔不在＝沒有工具），說明取工具定義的 description／parameters
tools = []
TOOLS = ["aos-tools", "--file", tools_file] + (["--overlay", overlay] if overlay else [])
if os.path.isfile(tools_file) or overlay:
    try:
        r = subprocess.run(TOOLS + ["ls", "--json"],
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.PIPE, text=True)            # stderr 不吞：aos-tools 自己說哪個工具壞
    except OSError as e:
        die("ToolsBad", "aos-tools cannot start: %s" % e)
    if r.returncode != 0:
        die("ToolsBad", "aos-tools ls exited %d" % r.returncode)
    for t in json.loads(r.stdout):
        function = {"name": t["name"]}
        function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in t["tooldef"]})
        tools.append({"type": "function", "function": function})

system_text = ""
if system_file:
    try:
        with open(system_file, encoding="utf-8") as f:
            system_text = f.read()                                       # 每次從檔讀，不存進 history
    except OSError as e:
        die("SystemMissing", "cannot read %s: %s" % (system_file, e))
memory = opts.get("--memory")
if memory and any(t["function"]["name"] == memory for t in tools):   # 這隻把 memory 拿掉了＝不給根
    try:
        p = subprocess.Popen(TOOLS + ["call", memory], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, start_new_session=True)   # 繼承自己的 stack；aos-tools call 算小格。stderr 不吞：工具自己說哪裡壞
    except OSError as e:
        die("MemoryFailed", "aos-tools cannot start: %s" % e)
    try:
        out, _ = p.communicate('{"op": "read"}', timeout=MEMORY_TIMEOUT_S)
    except subprocess.TimeoutExpired:            # 卡住的 memory 不讓 think 格一直卡（11-05 夜第二輪邊緣）：整群收掉
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(p.pid, sig)
                p.wait(2)
                break
            except subprocess.TimeoutExpired:
                continue
            except OSError:
                break
        die("MemoryFailed", "tool %s (op read of the root) did not finish in %d s (killed)" % (memory, MEMORY_TIMEOUT_S))
    if p.returncode != 0:
        die("MemoryFailed", "tool %s (op read of the root) exited %d" % (memory, p.returncode))
    root = out.strip()
    if root:
        system_text = (system_text.rstrip("\n") + "\n\n" if system_text.strip() else "") + \
            "Knowledge base root (from tool %s; call it for more):\n\n%s\n" % (memory, root)
system = [{"role": "system", "content": system_text}] if system_text else []


def read_cfg(path):
    """llm.json：一層物件；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        die("CfgBad", "cannot parse %s: %s" % (path, e))
    if not isinstance(d, dict):
        die("CfgBad", "%s must be a flat object" % path)
    return d


cfg = read_cfg(here("llm.json"))
cfg.update(read_cfg(os.path.join(stack, "llm.json")))   # stack 那份有的鍵蓋過定義（aos-agent llm set，每格重讀）
request = {"messages": system + history}
if tools:
    request["tools"] = tools
body = {"request": request}
if "endpoint" in cfg:
    if not isinstance(cfg["endpoint"], str) or not cfg["endpoint"]:
        die("CfgBad", "endpoint in llm.json must be a non-empty string")
    body["endpoint"] = cfg["endpoint"]

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
    die("WriteFailed", "cannot write %s: %s" % (path, e))
sys.exit(0)
