# brain.py [--system FILE] [--tools FILE] [--history full|task] [--max-tool-calls N] - think 格：帶 $AOS_STACK/history.jsonl（加 system、tools）組一份問腦的請求，寫 $AOS_STACK/think/request.json；不碰網路。
# 寄出去、收回信是下一格 wait（wait.py：aos-llm send／recv，經 $AOS_LLM_KERNEL〔llm kernel 的 stack〕的 llm kernel；thinking 2026-11-04 think-as-function 03 § 1）。
# 結束碼（fsm.json 照碼分岔，N-36）：0＝請求寫好了（→ wait）；10＝history 最後一則不是 user／tool（上一題已答完、或人改了 history）＝沒事做（→ idle）。
# 請求＝llm kernel 請求信的 body：{"endpoint"?: 代號, "request": {"messages", "tools"?, 調整鍵…}}（真正的模型名綁在 kernel 的 endpoint 包上）。
#   腦設定＝interfaces.json 宣告的 llm（AOS_CD）疊 $AOS_STACK/<宣告相對路徑>（只放改過的鍵，aos-agent llm set 寫的；有的鍵蓋過定義），每格重讀＝下一題生效；
#   鍵 model＝kernel 的包代號，填進 body 的 endpoint 欄（11-10 晚使用者「把fsm認的endpoint這個key，也改名爲model吧」；kernel 不動）；都沒寫＝不放（kernel 用預設）。
#   temperature、top_p、max_tokens、seed、presence_penalty、frequency_penalty、stop＝與快取無關的調整鍵，轉型後放進 request（llm_settings.py）。其他鍵不看（C-48）。
# 寫新請求時順手刪 $AOS_STACK/think/pending.txt（上一封的名字）：新請求取代舊的，wait 會重寄。
# --system FILE：讀成一則 system 放最前面、不存進 history（P-41）。沒給＝interfaces.json 宣告的 system（11-11 self-system，使用者裁「fsm 取代、eca 附加」）：
#   $AOS_STACK/<宣告相對路徑> 在＝整份用這隻自己那份（aos-agent system set／self_system 寫的，取代定義那份），否則定義那份；每格重讀＝下一格生效。
#   都不在、或沒宣告＝沒有 system；給了 --system＝照它、不看 stack（同 --tools）。文字空＝不送 system 訊息。
# --tools FILE：aos-tools 登記檔（預設 interfaces.json 宣告的 tools；沒有那份＝不給工具）；腦看到的工具名＝登記名。相對路徑從範本資料夾（AOS_CD）算。
#   沒給 --tools 時，$AOS_STACK/<宣告相對路徑> 在＝改用這隻自己那份（aos-agent tools add／rm 寫的，只存差異、"$override" 指回定義那份，11-10）。
# hook（lib/agent/hooks.py，圖紙 thinking/2026-11/10/self-family/hook）：有 tool_added hook 時，工具清單比上次（$AOS_STACK/hook_tools_seen.json）
#   多出來的名字一個觸發一次（第一次只記不觸發；沒有這種 hook＝刪那份檔）。hook 停下＝HookFailed／HooksBad 退 1。
# 錯：stderr 一行「agent-fsm: error: 代號 原因」、退 1（P-20）。--help 印英文用法；Ctrl-C 退 130。
# on_clock（11-11 thinking/2026-11/11/clock-hook）：這格一開頭先 hooks.clock_tick——時鐘走到了的 on_clock hook 才跑（handler 預設什麼都不做、history 不多東西）；沒有這種 hook＝只讀清單。
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
    if (Path(__file__).resolve().parent / "hooks.py").is_file():
        import hooks  # noqa: E402
    else:
        from agent import hooks  # noqa: E402
except (ModuleNotFoundError, ImportError) as _error:
    if _error.name not in ("aos_flags", "tool_io", "agent_files", "agent", "agent.agent_files", "hooks", "agent.hooks"):
        raise
    print("agent-fsm: error: ModuleMissing required Python module %s is unavailable" % _error.name,
          file=sys.stderr)
    sys.exit(1)
finally:
    for _path in _import_paths:
        sys.path.remove(_path)

HELP = """\
usage: brain.py [--system FILE] [--tools FILE] [--history full|task] [--max-tool-calls N]   (a cell of templates/agent-fsm; run by its fsm.json under aos-fsm, needs $AOS_STACK)
The think cell: build the request to the brain from $AOS_STACK/history.jsonl (plus system and
tools) and write $AOS_STACK/think/request.json. Exit 0 = written (go wait); 10 = nothing to answer.
--system FILE: a system message in front (default: the system file declared in interfaces.json,
this agent's own copy in $AOS_STACK when it has one); --tools FILE: the aos-tools registry;
--history full|task: include all history (default), or only messages from the last user.
--max-tool-calls N: omit tools after N calls in the current task (non-negative integer).
Hooks: with a tool_added hook, each tool name new since the last run (hook_tools_seen.json;
the first run only records) fires it once. A failing hook = HookFailed, exit 1.
On error: one line "agent-fsm: error: CODE reason" on stderr, exit 1.
"""
USAGE = HELP.splitlines()[0].removeprefix("usage: ")
signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）


def die(code, reason):
    if code == "ArgumentsBad":
        reason = "%s (usage: %s)" % (reason, USAGE)
    aos_flags.die("agent-fsm", code, reason)


def here(path):
    """相對路徑從範本資料夾（AOS_CD；沒設＝cwd）算。"""
    return os.path.join(os.environ.get("AOS_CD") or ".", path)


try:
    values, rest = aos_flags.parse(sys.argv[1:], {}, multi={'--system': '--system', '--tools': '--tools', '--history': '--history', '--max-tool-calls': '--max-tool-calls'}, help=HELP)
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
try:                                             # 11-11 on_clock：每格開頭看一次時鐘，到了才起 handler（hooks.clock_tick）
    hooks.clock_tick(os.environ.get("AOS_CD") or ".", stack, warn=lambda line: aos_flags.warn("agent-fsm", line))
except (hooks.HookFailed, hooks.HooksBad) as e:
    die(type(e).__name__, str(e))
try:
    files = declared_files(os.environ.get("AOS_CD") or ".")
except ValueError as e:
    die("InterfaceBad", str(e))
if "--system" not in opts and "system" in files:   # 11-11：這隻自己那份在＝整份用它（取代），否則定義那份；都不在＝沒有 system
    own_system = os.path.join(stack, files["system"])
    system_file = own_system if os.path.isfile(own_system) else here(files["system"])
    if not os.path.isfile(system_file):
        system_file = None
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
    listed = json.loads(r.stdout)
    for t in listed:
        function = {"name": t["name"]}
        function.update({k: t["tooldef"][k] for k in ("description", "parameters") if k in t["tooldef"]})
        tools.append({"type": "function", "function": function})
else:
    listed = []

try:                                             # tool_added：比上次多出來的名字，一個一次
    cd = os.environ.get("AOS_CD") or "."
    for added, where in hooks.tools_added(stack, [(t["name"], os.path.abspath(t["path"]) if t.get("path") else None)
                                                  for t in listed],
                                          hooks.has("tool_added", cd, stack)):
        hooks.fire("tool_added", {"name": added, "path": where}, cd, stack,
                   warn=lambda line: aos_flags.warn("agent-fsm", line))
except (hooks.HookFailed, hooks.HooksBad) as e:
    die(type(e).__name__, str(e))
except OSError as e:
    die("WriteFailed", "cannot write %s: %s" % (os.path.join(stack, hooks.SEEN), e))

system_text = ""
if system_file:
    try:
        with open(system_file, encoding="utf-8") as f:
            system_text = f.read()                                       # 每次從檔讀，不存進 history
    except OSError as e:
        die("SystemMissing", "cannot read %s: %s" % (system_file, e))
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
sys.dont_write_bytecode = True                             # 定義資料夾不留 __pycache__（P-15：定義不被寫）
import llm_settings  # noqa: E402  （範本資料夾在 sys.path 最前面）
request = {"messages": system + history}
if tools and (max_tool_calls is None or tool_call_count < max_tool_calls):
    request["tools"] = tools
body = {"request": request}
try:
    model, tuning = llm_settings.body_fields(cfg)
except ValueError as e:
    die("CfgBad", str(e))
request.update(tuning)
if model:
    body["endpoint"] = model                                  # agent 這邊叫 model，kernel 請求信照舊叫 endpoint

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
