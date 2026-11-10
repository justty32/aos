# brain.py [--system FILE] [--tools FILE] [--memory NAME] [--history full|task] [--max-tool-calls N] - think 格：帶 $AOS_STACK/history.jsonl（加 system、tools）組一份問腦的請求，寫 $AOS_STACK/think/request.json；不碰網路。
# 寄出去、收回信是下一格 wait（wait.py：aos-llm send／recv，經 $AOS_LLM_KERNEL〔llm kernel 的 stack〕的 llm kernel；thinking 2026-11-04 think-as-function 03 § 1）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝請求寫好了（→ wait）；10＝history 最後一則不是 user／tool（上一題已答完、或人改了 history）＝沒事做（→ idle）。
# 請求＝llm kernel 請求信的 body：{"endpoint"?: 代號, "request": {"messages", "tools"?}}（不寫 model：model 綁在 kernel 的 endpoint 包上）。
#   endpoint 來自 interfaces.json 宣告的 llm（AOS_CD）疊 $AOS_STACK/<宣告相對路徑>（只放改過的鍵，aos-agent llm set 寫的；有的鍵蓋過定義），每格重讀＝下一題生效；
#   都沒寫＝不放（kernel 用它自己的預設代號）。其他鍵不看（C-48）。
# 寫新請求時順手刪 $AOS_STACK/think/pending.txt（上一封的名字）：新請求取代舊的，wait 會重寄。
# --system FILE：讀成一則 system 放最前面、不存進 history（P-41）；沒給＝沒有 system。
# --memory NAME（11-05 晚 agent-knowledge K2）：登記名 NAME 的工具（memory）叫一次 {"op": "read"}，它印的知識庫根接在 system 後面、
#   同一則 system 訊息（每格重叫＝知識庫改了下一題就看到；不存進 history）。叫的是腦之後叫的同一個工具＝腦看到的根跟它自己查的一樣。
#   工具清單（疊覆蓋層後）沒有 NAME＝不給根（這隻把 memory 拿掉了）；叫了起不來、退非 0、或 30 秒沒叫完（整群收掉）＝
#   warning 一行（工具自己那行照樣在 stderr）、system 裡改放一句「Knowledge base is not available right now: 原因」、照樣寫請求
#   （11-10 TS，圖紙 07 K01：知識庫一時讀不到不擋問腦，狀態不壞；原本是 MemoryFailed 退 1）。
# --tools FILE：aos-tools 登記檔（預設 interfaces.json 宣告的 tools；沒有那份＝不給工具）；腦看到的工具名＝登記名。相對路徑從範本資料夾（AOS_CD）算。
#   沒給 --tools 時，$AOS_STACK/<宣告相對路徑> 在＝改用這隻自己那份（aos-agent tools add／rm 寫的，只存差異、"$override" 指回定義那份，11-10）。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1（P-20）。--help 印英文用法；Ctrl-C 退 130。照舊的 agent-eve 的 brain.py 改（11-04 隨 proto8/tests 刪了）（拿掉工作區題目認領與 current.txt）。
import json, os, signal, subprocess, sys
from pathlib import Path

_import_paths = [str(Path(__file__).resolve().parent)]
for _parent in Path(__file__).resolve().parents:
    for _layer, _module in (("py", "aos_flags.py"), ("lib", "agent/agent_files.py")):
        _root = _parent / _layer
        if (_root / _module).is_file() and str(_root) not in _import_paths:
            _import_paths.append(str(_root))
sys.path[:0] = _import_paths
try:
    import aos_flags  # noqa: E402
    if (Path(__file__).resolve().parent / "agent_files.py").is_file():
        from agent_files import declared_files  # noqa: E402
    else:
        from agent.agent_files import declared_files  # noqa: E402
except ModuleNotFoundError as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files"):
        raise
    print("agent-fsm: error: ModuleMissing required Python module %s is unavailable" % _error.name,
          file=sys.stderr)
    sys.exit(1)
finally:
    for _path in _import_paths:
        sys.path.remove(_path)

HELP = """\
usage: brain.py [--system FILE] [--tools FILE] [--memory NAME] [--history full|task] [--max-tool-calls N]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The think cell: build the request to the brain from $AOS_STACK/history.jsonl (plus system and
tools) and write $AOS_STACK/think/request.json. Exit 0 = written (go wait); 10 = nothing to answer.
--system FILE: a system message in front; --tools FILE: the aos-tools registry;
--history full|task: include all history (default), or only messages from the last user.
--max-tool-calls N: omit tools after N calls in the current task (non-negative integer).
--memory NAME: call tool NAME with {"op": "read"} and append the knowledge base root it prints
to the system message (skipped when NAME is not among the tools). If that call fails or
takes over 30 s, one warning line goes to stderr, the system message says "Knowledge base is
not available right now: <reason>" instead, and the request is written as usual.
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
USAGE = HELP.splitlines()[0].removeprefix("usage: ")
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）
MEMORY_TIMEOUT_S = 30                           # --memory 叫根的逾時（11-05 夜第二輪邊緣：原本沒逾時，memory 卡住＝think 格卡住）


def die(code, reason):
    if code == "ArgumentsBad":
        reason = "%s (usage: %s)" % (reason, USAGE)
    aos_flags.die("agent-fsm", code, reason)


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


try:
    values, rest = aos_flags.parse(sys.argv[1:], {}, multi={'--system': '--system', '--tools': '--tools', '--memory': '--memory', '--history': '--history', '--max-tool-calls': '--max-tool-calls'}, help=HELP)
except aos_flags.Error as e:
    die(e.code, e)
if rest:
    die("ArgumentsBad", "unexpected argument %s" % rest[0])
# 收齊重複值再取最後一個：任一次空值都照舊報錯，不讓後面的值蓋掉錯誤。
for flag, items in values.items():
    if any(not value for value in items):
        die("ArgumentsBad", "%s needs a non-empty value" % flag)
opts = {flag: items[-1] for flag, items in values.items()}
history_mode = opts.get("--history", "full")
if history_mode not in ("full", "task"):
    die("ArgumentsBad", "--history must be full or task")
max_tool_calls = opts.get("--max-tool-calls")
if max_tool_calls is not None:
    if not max_tool_calls.isascii() or not max_tool_calls.isdecimal():
        die("ArgumentsBad", "--max-tool-calls must be a non-negative integer")
    max_tool_calls = int(max_tool_calls)
system_file = here(opts["--system"]) if "--system" in opts else None
if system_file and not os.path.isfile(system_file):
    die("SystemMissing", "system file not found: %s" % system_file)
stack = os.environ.get("AOS_STACK")
if not stack:
    die("StackMissing", "AOS_STACK is not set")
try:
    files = declared_files(os.environ.get("AOS_CD") or ".")
except ValueError as e:
    die("InterfaceBad", str(e))
tools_rel = opts.get("--tools", files.get("tools"))
tools_file = os.path.join(os.environ.get("AOS_CD") or ".", tools_rel) if tools_rel else None
if "--tools" in opts and not os.path.isfile(tools_file):
    die("ToolsMissing", "tool registry not found: %s" % tools_file)
own = os.path.join(stack, tools_rel) if tools_rel and "--tools" not in opts else None
if own and os.path.isfile(own):                   # 這隻自己那份（$override 定義那份，aos-tools 疊；11-10 aos-tools-cli 步 4）在就用它
    tools_file = own

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

task_start = max((i for i, m in enumerate(history) if m.get("role") == "user"), default=0)
task_history = history[task_start:]
tool_call_count = sum(len(m.get("tool_calls") or []) for m in task_history
                      if m.get("role") == "assistant")
if history_mode == "task":
    history = task_history

# tools：登記檔裡的工具（aos-tools ls --json；登記檔不在＝沒有工具），說明取工具定義的 description／parameters
tools = []
TOOLS = ["aos-tools"] + (["--file", tools_file] if tools_file else [])
if tools_file and os.path.isfile(tools_file):
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


def memory_root():
    """叫 memory 拿知識庫根：(根, None)；叫不成＝(None, 原因)（11-10 TS，圖紙 07 K01：知識庫一時讀不到不擋問腦）。"""
    try:
        p = subprocess.Popen(TOOLS + ["call", memory], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, start_new_session=True)   # 繼承自己的 stack；aos-tools call 算小格。stderr 不吞：工具自己說哪裡壞
    except OSError as e:
        return None, "aos-tools cannot start: %s" % e
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
        return None, "tool %s (op read of the root) did not finish in %d s (killed)" % (memory, MEMORY_TIMEOUT_S)
    if p.returncode != 0:
        return None, "tool %s (op read of the root) exited %d" % (memory, p.returncode)
    return out.strip(), None


if memory and any(t["function"]["name"] == memory for t in tools):   # 這隻把 memory 拿掉了＝不給根
    root, why = memory_root()
    if why:                                      # 讀不到知識庫：warning 一行、照樣問腦，system 裡說一句（狀態不壞）
        aos_flags.warn("agent-fsm", "%s; asking the brain without the knowledge base" % why)
        root = "Knowledge base is not available right now: %s" % why
    elif root:
        root = "Knowledge base root (from tool %s; call it for more):\n\n%s" % (memory, root)
    if root:
        system_text = (system_text.rstrip("\n") + "\n\n" if system_text.strip() else "") + root + "\n"
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


cfg = read_cfg(here(files["llm"])) if "llm" in files else {}
if "llm" in files:
    cfg.update(read_cfg(os.path.join(stack, files["llm"])))   # stack 那份有的鍵蓋過定義（aos-agent llm set，每格重讀）
request = {"messages": system + history}
if tools and (max_tool_calls is None or tool_call_count < max_tool_calls):
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
