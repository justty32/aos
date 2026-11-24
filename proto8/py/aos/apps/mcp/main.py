# aos-mcp - 把 aos-tools 的工具註冊檔（登記檔，例 tools.json）登記的工具當 MCP tools 給外部 agent（Claude Code、pi coding agent 等）叫；stdio JSON-RPC
# 白話版：這支是「翻譯櫃台」，包在 aos-tools 上面（使用者 10-27「aos-mcp 是一個小包裝，跑在 aos-tools 上」）。
# 外面的 agent 只會講 MCP；櫃台把「有哪些工具」交給 `aos-tools ls --json`、「叫一次」交給 `aos-tools call 名`，
# 自己不懂任何一個工具在做什麼、也不管工具是資料夾、JSON 還是可執行檔（C-52）。設計：proto8/thinking/2026-10/28/aos-tools/README.md。
#
# 用法：aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] [--enable-logs [--logs-path FILE]] [REGISTRY...]
#   這隻自己加減的工具（11-10 aos-tools-cli 步 4）：給 stack 那份登記檔就好——它的 "$override" 指回定義那份，疊法歸 aos-tools。
#   每個 REGISTRY 是一份登記檔的路徑（相對路徑從啟動時的 cwd 算；不是檔＝ToolMissing）；檔名不限
#   （11-02 使用者「改成指定檔案」，以前給的是 agent 資料夾、讀它的 tools.json）。一份都沒給＝./tools.json
#   （11-02 使用者「不接，就是默認aos-tools.json」先改成 ./aos-tools.json；11-02 再改回 ./tools.json、跟 aos-tools 一致：
#   使用者「兩邊的json格式是一樣的嗎？是同一份嗎？是的話，那就全部改回預設tools.json。」；不存在＝ToolMissing）。好幾份的工具合在一起，撞名＝ToolsBad。
#   清單每次 tools/list、tools/call 都重讀（登記檔變了，下次列就看得到）。11-10 深夜（tools-def，使用者「3.同一輪就生效」）：
#   --own FILE＝這隻自己那份登記檔（stack 裡、"$override" 定義那份）：每次讀清單先看它在不在，在＝只用它、不在＝用 REGISTRY
#   （session 開始時還沒有、self_tools 第一次 add 才建出來的那份，同一輪也看得到）。cli_session 起它時帶上。
#   initialize 宣告 tools.listChanged；每次 tools/call 回完再讀一次清單，跟上次給出去的不一樣（腦用 self_tools 加減了工具）
#   就送一則 notifications/tools/list_changed，用戶端（Claude Code）重拿 tools/list，同一輪就叫得到新工具。
#   工作區＝--ws ＞ $AOS_WS；stack＝--stack ＞ $AOS_STACK ＞ $WS/.stack/。每次叫工具：
#   AOS_WS=WS AOS_STACK=<stack> aos-tools --file REGISTRY call 名（aos-tools 算 tools/<名>/ 小格；兩支指令由 PATH 找，呼叫者放好），
#   arguments 進 stdin、stdout 整段回去，退非 0＝isError（失敗時另附工具 stderr 的最後 STDERR_TAIL 位元組，見 tail_of）；逾時＝工具 _metainfo（資料夾的 _metainfo.json 檔／JSON 檔的 _metainfo key）的 timeout_ms，沒寫或壞了（另印一行提醒）用 --timeout-s（預設 60），
#   兩者 0 都是不設上限；到了整群 TERM、2 秒後 KILL。呼叫紀錄預設不記（11-02 使用者「默認不留」）：給 --enable-logs＝每次叫完在
#   <stack>/aos-mcp-logs.jsonl 記一行（名字、arguments、結束碼、花多久），再加 --logs-path FILE＝記在 FILE（相對路徑從啟動時的 cwd 算）；
#   只給 --logs-path、沒給 --enable-logs＝ArgumentsBad。
#   --hooks DEF（11-10 hook，圖紙 thinking/2026-11/10/self-family/hook § 6 eca 縮水版）：DEF＝定義資料夾（interfaces.json 最外層的 hookeds，11-21 起），stack＝上面那個 stack；
#   cli_session 起它時帶上。tools/call 跑之前 before_tool（name、id＝請求 id 轉字串、arguments；可改 arguments、攔下＝不跑，結果文字＝hook stdout，
#   空就「[aos] hook: tool NAME blocked by hook HOOK.」，不算 isError）、跑完 after_tool（加 content、code〔逾時 null〕、timed_out；可改 content）。
#   hook 停下（before_tool 的 hook 失敗＝HookFailed、清單壞＝HooksBad）＝這次 tools/call 回 isError、文字是那行錯，櫃台不死；after_tool 的 hook 失敗＝stderr 一行 warning（11-21 agent 一家的規矩，aos.agentlib.hooks）。沒給＝沒有 hook。
# 只做 initialize、ping、tools/list、tools/call（與 notifications/cancelled）；沒有 progress、resources、prompts、HTTP。
#   11-24 晚（線 home-listen-1124）：tools/call 各開一條執行緒同時跑，回覆照 id 回；_metainfo "parallel": false 的工具同名排隊；
#   notifications/cancelled＝收掉那次的行程群、不回；收發台在 serve.py。
# 錯：自己的錯 stderr 一行「aos-mcp: error: 代號 原因」、退 1（ArgumentsBad、FlagUnknown、WsMissing、ToolMissing、ToolsBad；11-05 stdio-unify R1）。
#   --help＝英文說明到 stdout、退 0（R3）；不給參數照常（讀 ./tools.json）；Ctrl-C＝退 130、不吐 traceback（R12）。
#   啟動時 aos-tools ls 失敗＝ToolsBad（aos-tools 自己那行照樣在 stderr）；跑起來之後重讀失敗＝那一則 JSON-RPC 回錯誤、不退
#   （錯誤訊息附 aos-tools 那次 stderr 的最後一段）。
#   工具與 aos-tools 的 stderr：aos-mcp 接住後原樣轉印到自己的 stderr（MCP 用戶端的 log）；失敗時最後一段另附給外部 agent
#   （11-05 使用者選「附 stderr 尾巴（推薦）」，edge-basics 題 1；C-52 的明文例外：出口是給外部 agent 看原因，11-05 R10 照舊）。成功時不附。
#   命令列形狀照 CONVENTION P-44（11-04）：旗標都在 REGISTRY 前面、`--` 結束旗標、`--x V`／`--x=V`；不認得的旗標＝FlagUnknown。
import json, os, subprocess, sys, threading, time

from aos import flags as aos_flags  # noqa: E402  proto8/py/aos/flags.py：P-44 的解析
from aos import metainfo  # noqa: E402
from aos import process_group  # noqa: E402  py/aos/process_group.py：逾時收整群（TERM→等→KILL）
from aos.agentlib import agent_hooks  # noqa: E402  py/aos/agentlib/agent_hooks.py：hook 遙控器，before_tool／after_tool（--hooks DEF）
from aos.apps.mcp import serve  # noqa: E402  py/aos/apps/mcp/serve.py：收發台（tools/call 同時跑、同名排隊、取消）

NAME = "aos-mcp"
PROTOCOL = "2025-06-18"                         # 對方沒講版本時回這個
USAGE = "aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] [--enable-logs [--logs-path FILE]] [--hooks DEF] [--own FILE] [REGISTRY...]"
OWN = None                                      # --own FILE（11-10 深夜 tools-def）：這隻自己那份登記檔；在＝用它代替 REGISTRY（每次重看，self_tools 第一次加就建出來）
HOOKS = None                                    # --hooks DEF（11-10）：定義資料夾的絕對路徑；None＝沒有 hook
H = None                                        # hook 遙控器（main 開一次；HOOKS None＝空遙控器，什麼都不跑、原樣回）
SERVER = serve.Server()                         # 收發台（stdout 一次一則、parallel false 的工具同名排隊）
HOOK_TURN = threading.Lock()                    # hook 一次一個：同一個 hook 的小格（<stack>/hookeds/<名>/event.json）同時寫會撞（11-24 實測）；工具本身照樣同時跑
DEFAULT_REGISTRY = "tools.json"               # 一份都沒給時讀 ./tools.json（跟 aos-tools 一致；11-02 改回）
LOGS_NAME = "aos-mcp-logs.jsonl"         # --enable-logs 沒給 --logs-path 時記在 <stack>/ 底下的這個檔（11-02）
LOGS_PATH = None                               # 記呼叫紀錄的檔（絕對路徑）；None＝不記（預設）
STDERR_TAIL = 2048                             # 失敗時附給外部 agent 的 stderr 最後幾個位元組（11-05，edge-basics 題 1）
aos_flags.HELP = """aos-mcp - serve the tools of aos-tools registries as MCP tools to an external agent (Claude Code, pi...); stdio JSON-RPC.

    aos-mcp [--ws WS] [--stack DIR] [--timeout-s N] [--enable-logs [--logs-path FILE]] [--hooks DEF] [--own FILE] [REGISTRY...]

Short flags: -w = --ws, -s = --stack, -h = --help.
REGISTRY: registry files (relative to the cwd at start; none = ./tools.json); several are merged, a name clash = ToolsBad.
  A registry may "$override" another one (aos-tools merges them); give an agent's own registry in its stack.
  The list is re-read on every tools/list and tools/call; when a call changed it (self_tools add/rm),
  a notifications/tools/list_changed follows the reply, so the client lists again at once.
Workspace = --ws > $AOS_WS; stack = --stack > $AOS_STACK > WS/.stack/. Each call runs
  AOS_WS=WS AOS_STACK=<stack> aos-tools --file REGISTRY call NAME (aos-tools selects tools/NAME/); arguments go to stdin, stdout goes back as the
  result, exit non-zero = isError (the last 2048 bytes of the tool's stderr are attached). Timeout = the tool's _metainfo timeout_ms,
  otherwise --timeout-s (default 60; a bad timeout_ms = a warning and this); 0 = no limit for either. Then TERM to the whole group, KILL 2 s later.
Calls run at the same time (a long wait does not hold the others); replies go back by request id. A tool whose _metainfo says
  "parallel": false runs one call at a time (calls to it wait in turn). notifications/cancelled stops that call's process group, no reply.
--hooks DEF: DEF is the agent definition folder (the hookeds of its interfaces.json; the stack copy goes on top). On tools/call,
  before_tool may change the arguments or block the call (the result text = the hook's stdout, or "[aos] hook: tool NAME blocked by hook HOOK.";
  not an error), after_tool may change the result text. A failing before_tool hook = that call returns isError with a HookFailed
  line; a failing after_tool hook = one warning line. No --hooks = no hooks.
--own FILE: the agent's own registry (in its stack); whenever it exists it is used instead of REGISTRY
  (checked on every read, so one made by the first self_tools add counts at once).
--enable-logs: log one line per call to <stack>/aos-mcp-logs.jsonl (or --logs-path FILE). Off by default.
Supports initialize, ping, tools/list, tools/call (and notifications/cancelled) only.
Errors: one stderr line `aos-mcp: error: CODE reason`, exit 1. Codes: ArgumentsBad, FlagUnknown, WsMissing, ToolMissing, ToolsBad.
  stderr of the tools and of aos-tools is passed through to aos-mcp's stderr."""


class ToolsBad(Exception):
    def __init__(self, msg, tail=""):
        super().__init__(msg)
        self.tail = tail                         # aos-tools 那次 stderr 的最後一段（跑起來之後回給外部 agent 用）


def tail_of(err, echo=True):
    """stderr（bytes）→ 原樣轉印到自己的 stderr（echo=False＝不轉印，叫的人自己決定），回最後 STDERR_TAIL 位元組（去頭尾空白；沒東西＝""）。"""
    if not err:
        return ""
    if echo:
        sys.stderr.buffer.write(err)
        sys.stderr.buffer.flush()
    t = err[-STDERR_TAIL:].decode("utf-8", "replace").strip()
    return ("..." + t) if len(err) > STDERR_TAIL else t


def die(code, reason):
    aos_flags.die(NAME, code, reason)


def parse_args(argv):
    """命令列 → (ws, stack, timeout_s, registries)；--enable-logs／--logs-path 設進 LOGS_PATH。"""
    global LOGS_PATH, HOOKS, OWN
    try:
        opts, files = aos_flags.parse(argv, {"--ws": "ws", "--stack": "stack", "--timeout-s": "timeout_s",
                                             "--logs-path": "log",
                                             "--hooks": "hooks", "--own": "own"}, {"--enable-logs": "enable"}, short=("-w", "-s"), anywhere=True)
    except aos_flags.Error as e:
        die(e.code, "%s (usage: %s)" % (e, USAGE))
    ws, stack = opts.get("ws", os.environ.get("AOS_WS")), opts.get("stack", os.environ.get("AOS_STACK"))
    enable, log, timeout_s = opts.get("enable", False), opts.get("log"), 60.0
    if "timeout_s" in opts:
        try:
            timeout_s = float(opts["timeout_s"])
        except ValueError:
            die("ArgumentsBad", "--timeout-s must be a number")
    if log is not None and not enable:
        die("ArgumentsBad", "--logs-path given without --enable-logs (give both to log; nothing is logged by default)")
    if log == "":
        die("ArgumentsBad", "--logs-path needs a file name")
    if "hooks" in opts:
        if not opts["hooks"] or not os.path.isdir(opts["hooks"]):
            die("ArgumentsBad", "--hooks needs the agent definition folder, got %r" % opts["hooks"])
        HOOKS = os.path.abspath(opts["hooks"])
    if "own" in opts:
        if not opts["own"]:
            die("ArgumentsBad", "--own needs the path of the agent's own registry (it may not exist yet)")
        OWN = os.path.abspath(opts["own"])
    if not files:
        files = [DEFAULT_REGISTRY]
    if not ws or not os.path.isdir(ws):
        die("WsMissing", "no --ws and no AOS_WS, or it is not a folder")
    regs = []
    for f in files:
        if not os.path.isfile(f):
            die("ToolMissing", "%s is not a file (give the path of a registry, e.g. tools.json; register tools with aos-tools --file it add)" % f)
        regs.append(os.path.abspath(f))
    ws = os.path.abspath(ws)
    stack = os.path.abspath(stack) if stack else os.path.join(ws, ".stack")
    if enable:
        LOGS_PATH = os.path.abspath(log) if log else os.path.join(stack, LOGS_NAME)
    return ws, stack, timeout_s, regs


def annotations(meta):
    """_metainfo → MCP 的提示（只搬幾個布林，數字不搬：M10 模型看不到）。沒寫的 key 就不給。"""
    out = {}
    if isinstance(meta.get("side_effect"), bool):
        out["readOnlyHint"] = not meta["side_effect"]
    if isinstance(meta.get("idempotent"), bool):
        out["idempotentHint"] = meta["idempotent"]
    res = meta.get("resource")
    if res is not None:
        res = res if isinstance(res, list) else [res]
        out["openWorldHint"] = any(r in ("llm", "net") for r in res)
    return out


def tools_argv(reg):
    return ["aos-tools", "--file", reg]


OWN_BAD = [None]                                  # 上一次說過的「自己那份壞了」原因（同一個原因只說一次）


def load_tools(regs):
    """問 aos-tools 每份註冊檔登記了什麼 → {名: {reg, spec, max_s}}；失敗丟 ToolsBad。--own 那份在＝只用它（每次重看）。
    11-24：--own 那份自己壞了（aos-tools ls 退非 0）＝stderr 一行 warning、改用 REGISTRY（定義那份：信箱等基本工具保得住），
    修好或刪掉之後下一次重讀就回到它。REGISTRY 也壞＝照舊 ToolsBad。疊進來的某份 pack 壞＝aos-tools 只跳過那份（它自己印 warning）。"""
    if OWN and os.path.isfile(OWN):
        try:
            got = _load([OWN])
            OWN_BAD[0] = None
            return got
        except ToolsBad as e:
            if str(e) != OWN_BAD[0]:
                OWN_BAD[0] = str(e)
                aos_flags.warn(NAME, "the agent's own registry %s cannot be read (%s); using the definition's tools (%s) until it is "
                               "fixed (aos-agent tools reset deletes it)" % (OWN, e, ", ".join(regs)))
    return _load(regs)


def _load(regs):
    tools = {}
    for reg in regs:
        try:
            r = subprocess.run(tools_argv(reg) + ["ls", "--json"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)   # stderr 接住、照樣轉印（tail_of）
        except OSError as e:
            raise ToolsBad("cannot run aos-tools: %s" % e)
        tail = tail_of(r.stderr)
        if r.returncode != 0:
            raise ToolsBad("aos-tools ls %s exited %d" % (reg, r.returncode), tail)
        for t in json.loads(r.stdout.decode("utf-8")):
            if t["name"] in tools:
                raise ToolsBad("duplicate tool name: %s (%s and %s)" % (t["name"], tools[t["name"]]["reg"], reg))
            td, meta = t["tooldef"], t.get("metainfo") or {}
            spec = {"name": t["name"], "description": td.get("description", ""),
                    "inputSchema": td.get("parameters", {"type": "object", "properties": {}})}
            hints = annotations(meta)
            if hints:
                spec["annotations"] = hints
            notes = []                           # metainfo 只是參考：壞的 timeout_ms＝沒寫＝用 --timeout-s，提醒一行
            milliseconds = metainfo.timeout_ms(meta, notes)
            for note in notes:
                aos_flags.warn(NAME, "tool %s: %s; using --timeout-s" % (t["name"], note))
            max_s = milliseconds / 1000.0 if milliseconds is not None else None
            tools[t["name"]] = {"reg": reg, "spec": spec, "max_s": max_s,
                                "parallel": meta.get("parallel") is not False}   # 只有明寫 false 才排隊（tool_spec 的預設是 true）
    return tools


def call(name, tool, args, ws, stack, timeout_s, echo=True, job=None):
    """跑一次工具 → (結束碼, stdout, stderr 最後一段, 花幾毫秒, 逾時秒數)。結束碼 None＝逾時被收掉。job＝serve.Job（起了行程就交給它，取消時收）。"""
    env = dict(os.environ, AOS_WS=ws, AOS_STACK=stack)   # 工具小格統一由 aos-tools call 算（P-17）
    # AOS_ENTRY 照常繼承（11-04 四元素審查：原本 pop 掉、怕外面殘留的值讓工具找錯入口；但 P-39 是一路繼承、使用者 11-01 裁留，外面設了＝要它）
    limit = tool["max_s"] if tool["max_s"] is not None else timeout_s
    t0 = time.monotonic()
    p = subprocess.Popen(tools_argv(tool["reg"]) + ["call", name], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                         start_new_session=True)   # 自成一群：逾時能整群收掉（P-36）
    if job is not None:
        job.started(p)
    try:
        out, err = p.communicate(json.dumps(args).encode(), timeout=None if limit == 0 else limit)
        code = p.returncode
    except subprocess.TimeoutExpired:
        process_group.stop(p, 2, 2)              # TERM 整群、等 2 秒；還在就 KILL、再等 2 秒（py/aos/process_group.py）
        try:
            out, err = p.communicate(timeout=2)  # 整群收掉了：管子另一頭多半都關了
        except subprocess.TimeoutExpired:        # 有逃出群組的還拿著管子：不等了
            out, err = b"", b""
        code = None
    tail = tail_of(err, echo)
    return code, out.decode("utf-8", "replace"), tail, int((time.monotonic() - t0) * 1000), limit


def record(line):
    if LOGS_PATH is None:                       # 預設不記
        return
    os.makedirs(os.path.dirname(LOGS_PATH), exist_ok=True)
    with open(LOGS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


class HookStop(Exception):
    """hook 停下：這次 tools/call 回 isError（櫃台不死）。"""


def hook_stop(code, sentence):
    """hook 遙控器的 fail：丟 HookStop 帶那一行錯（tools_call 把它變成這次的 isError）。"""
    raise HookStop(aos_flags.error_line(NAME, code, sentence))


def tools_call(params, tools, ws, stack, timeout_s, mid=None, job=None):
    try:
        name = params.get("name")
        if name not in tools:
            return None, (-32602, "no such tool: %s" % name)
        with SERVER.gate(name, tools[name].get("parallel", True)):   # parallel false＝同名一次一份
            if job is not None and job.cancelled:                   # 排隊時被取消了：不跑（也不會回）
                return None, (-32800, "request cancelled")
            return run_tool(params, tools, ws, stack, timeout_s, mid, job)
    except HookStop as e:
        return {"content": [{"type": "text", "text": str(e)}], "isError": True}, None


def run_tool(params, tools, ws, stack, timeout_s, mid, job=None):
    name, args = params.get("name"), params.get("arguments") or {}
    cid = "" if mid is None else str(mid)
    with HOOK_TURN:
        verdict, args = H.guard_tool(name, cid, args)
    if verdict == "blocked":                    # 攔下：不跑、不記、不觸發 after_tool；args＝給外部 agent 看的字
        return {"content": [{"type": "text", "text": args}], "isError": False}, None
    code, out, tail, ms, limit = call(name, tools[name], args, ws, stack, timeout_s, job=job)
    record({"name": name, "arguments": args, "code": code, "elapsed_ms": ms,
                   "called_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    if code is None:
        text = aos_flags.error_line(NAME, "CommandFailed", "%s timed out (%g s); its process group was killed" % (name, limit))
    elif code != 0 and not out.strip():
        text = aos_flags.error_line(NAME, "CommandFailed", "%s exited %d with empty stdout" % (name, code))
    else:
        text = out
    content = [{"type": "text", "text": text}]
    if code != 0 and tail:                      # 失敗時附 stderr 尾巴，外部 agent 才看得到原因（11-05，edge-basics 題 1）
        content.append({"type": "text", "text": "%s\n%s" % (aos_flags.aos_note("tool", "%s stderr (last %d bytes at most):" % (name, STDERR_TAIL)), tail)})
    with HOOK_TURN:
        after = H.fire("after_tool", {"name": name, "id": cid, "arguments": args, "content": "\n".join(c["text"] for c in content),
                                      "code": code, "timed_out": code is None})
    if "content" in after["changed"]:           # hook 改了結果：整段換成它給的一段文字
        content = [{"type": "text", "text": after["data"]["content"]}]
    return {"content": content, "isError": code != 0}, None


def handle(msg, regs, ws, stack, timeout_s, job=None):
    """一則 JSON-RPC → 回覆（通知不回，傳回 None）。"""
    method, params, mid = msg.get("method"), msg.get("params") or {}, msg.get("id")
    if mid is None:                             # 通知（notifications/initialized 等）：不用回
        return None
    result, err = None, None
    try:
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", PROTOCOL),
                      "capabilities": {"tools": {"listChanged": True}}, "serverInfo": {"name": NAME, "version": "0.2"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [t["spec"] for t in load_tools(regs).values()]}
        elif method == "tools/call":
            result, err = tools_call(params, load_tools(regs), ws, stack, timeout_s, mid, job)
        else:
            err = (-32601, "method not supported: %s" % method)
    except ToolsBad as e:                       # 跑起來之後登記檔壞了：這一則回錯，不退
        err = (-32603, aos_flags.error_line(NAME, "ToolsBad", e) + ("\nstderr (last part):\n%s" % e.tail if e.tail else ""))
    if err:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": err[0], "message": err[1]}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def signature(tools):
    """給出去的清單長怎樣（名字＋給模型的 spec）；變了才通知 list_changed。"""
    return json.dumps([tools[n]["spec"] for n in sorted(tools)], sort_keys=True)


def main():
    global H
    ws, stack, timeout_s, regs = parse_args(sys.argv[1:])
    H = agent_hooks.open(HOOKS, stack, fail=hook_stop, warn=lambda line: aos_flags.warn(NAME, line))
    try:
        shown = [signature(load_tools(regs))]   # 啟動時先讀一次：壞了就別開櫃台；之後是最後一次給出去的清單
    except ToolsBad as e:
        die("ToolsBad", str(e))
    seen = threading.Lock()

    def relist(notify):
        """重讀清單、記成最後給出去的；notify（tools/call 做完）且跟上次不一樣＝回 [list_changed]（收發台緊跟在回覆後面送；
        腦剛加減了工具，同一輪就生效），不然 []。"""
        try:
            now = signature(load_tools(regs))
        except ToolsBad:
            return []                           # 登記檔這時壞了：下一則照常回錯，這裡不通知
        with seen:
            changed, shown[0] = now != shown[0], now
        return [{"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}] if notify and changed else []

    SERVER.after = lambda: relist(True)
    for line in sys.stdin:                      # 一行一則（MCP stdio 傳輸）
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError as e:
            SERVER.send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON: %s" % e}})
            continue
        if not isinstance(msg, dict):
            SERVER.send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "must be a JSON object"}})
            continue
        method = msg.get("method")
        if method == "tools/call" and msg.get("id") is not None:   # 一則一條執行緒：長等的不擋別的
            SERVER.spawn(msg["id"], lambda job, msg=msg: handle(msg, regs, ws, stack, timeout_s, job))
            continue
        if method == "notifications/cancelled":
            rid = (msg.get("params") or {}).get("requestId")
            if rid is not None:
                SERVER.cancel(rid)
            continue
        reply = handle(msg, regs, ws, stack, timeout_s)
        if reply is not None:
            SERVER.send(reply)
            if method == "tools/list":
                relist(False)
    SERVER.wait()                               # stdin 讀完：還在跑的回完再走


if __name__ == "__main__":
    aos_flags.run(main)
