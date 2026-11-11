"""agents_cmd - subagent 與 agents_ctl 共用：查鍵、組 aos-agent ctl 各動作的旗標、跑 aos-agent（或旁邊的 self_*）並把下層錯翻成自己的。

不是工具（沒有 _entry）；兩支工具的 _entry 把 lib/agent/ 放上 sys.path 後 import 它。錯誤行一律走 tool_io.die（名字是 tool_io.start 記的那支）。
來由：thinking 2026-11/10/agents-split 02 施工單「兩支組 ctl add 旗標的程式共用一份」；跑子行程那段（分段等、TERM 先收那一群、下層最後一行錯誤行的
代號與原因接成自己的，C-52 例外 ⑤）從舊 agents/_entry 搬來。參數跟 aos-agent ctl 一對一：不多給、不多擋；給了才轉（沒給＝下層的預設）。
相對路徑一律交給下層、cwd＝$AOS_WS（aos-agent 從目前目錄算），這層不換算。
"""
import json, math, os, re, signal, subprocess, sys, time

import tool_io

STEP_S = 90                    # 一般步驟的子行程保險；等 daemon 的動作另取 max(STEP_S, timeout_s + 30)
CTL_DEFAULT_S = 30             # aos-agent ctl 的 --timeout-s 預設（只用來算保險，不替下層填值）
LISTEN_DEFAULT_S = 600         # listen／ask 什麼期限都沒給時等幾秒
MAX_CYCLES = 9223372036854775807 - 30
TOOL_WORDS = {"InstanceExists": 'give another "name", or remove that agent first with {"op": "rm", "name": ...}'}
# 下層成功句／錯誤句裡教 CLI 的寫法 → 工具參數的寫法（腦手上沒有 CLI；11-10 驗收怪處 3）
CLI_WORDS = ((re.compile(r"aos-agent ctl (start|wake|resume) --target (\S+)"), r'{"op": "\1", "name": "\2"}'),
             (re.compile(r"delete it with aos-agent ctl rm --purge, or by hand"), 'to delete it: add it again under the same name, then rm with "purge": true'),
             (re.compile(r"add --replace to replace it"), 'add "replace": true to replace it'),
             (re.compile(r"the stack may still be there: aos-agent ctl add with the same name"), 'the stack may still be there: {"op": "add"} with the same name'))


def tool_words(text):
    for pattern, new in CLI_WORDS:
        text = pattern.sub(new, text)
    return text


ERR_AOS = re.compile(r"aos-[a-z-]+: error: ([A-Z][A-Za-z]+) (.*)\Z")
QUEUED_RE = re.compile(r"queued .+ at position [0-9]+ \(letter ([^;]+); applied when a slot frees\)")
# ctl add 收的鍵（subagent 的 add、agents_ctl 的 add 同一排）
ADD_KEYS = ("def", "def_json", "name", "ws", "ws_json", "stack", "stack_json", "limits", "envs", "auto_restart", "timeout_s", "on_queued")
# 帶目標的生滅停起：op → 收的鍵（name 一定要）
LIFE_OPS = {"rm": ("name", "purge", "timeout_s"),
            "stop": ("name", "timeout_s"), "sleep": ("name", "timeout_s"),
            "start": ("name", "timeout_s", "on_queued"), "wake": ("name", "timeout_s", "on_queued"),
            "pause": ("name",), "resume": ("name",), "state": ("name",)}
die = tool_io.die
child = None


# ---- 子行程 ----
def kill_group(p):
    for sig, wait_s in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        try:
            os.killpg(p.pid, sig)
        except OSError:
            return
        try:
            p.wait(wait_s)
            return
        except subprocess.TimeoutExpired:
            pass


def _on_term(signum, frame):
    if child is not None:
        kill_group(child)
    sys.exit(128 + signum)


def install_signals():
    """TERM 與 Ctrl-C：先收掉正在跑的那一群再走（lib 契約規則 5；Ctrl-C 退 130、不吐 traceback）。"""
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)


def run(cmd, text=None, timeout_s=STEP_S, timeout_cycles=None, env=None, err_re=ERR_AOS):
    """跑 cmd（cwd＝$AOS_WS）；退 0 回 (stdout, None)，退非 0 回 (stdout, (代號, 原因))：取它 stderr 裡最後一行符合 err_re 的，沒有＝CommandFailed。
    stderr 原樣透到自己的 stderr（R10）。timeout_cycles 給了＝照兩鐘期限短輪詢；不然 timeout_s 秒（分段等，每段最多一天）。"""
    global child
    try:
        deadline = tool_io.deadline_after(timeout_cycles) if timeout_cycles is not None else None
    except tool_io.Error as e:
        die(e.code, str(e))
    cwd = tool_io.workspace()
    try:
        child = subprocess.Popen(cmd, stdin=subprocess.PIPE if text is not None else subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, start_new_session=True, cwd=cwd, env=env)
    except OSError as e:
        die("LaunchFailed", "cannot start %s (is it on PATH? proto8/install.sh puts aos-agent there): %s" % (cmd[0], e))
    what = " ".join([os.path.basename(cmd[0])] + list(cmd[1:3]))
    try:
        end = time.monotonic() + timeout_s
        payload = None if text is None else text.encode("utf-8")
        while True:
            try:
                out, err = child.communicate(payload, timeout=0.2 if deadline is not None else min(86400, max(0, end - time.monotonic())))
                break
            except subprocess.TimeoutExpired:
                payload = None
                if (not tool_io.expired(deadline)) if deadline is not None else time.monotonic() < end:
                    continue
                die("CommandFailed", "%s did not finish in %s (killed)" %
                    (what, "%d cycles" % timeout_cycles if deadline is not None else "%g s" % timeout_s))
    except tool_io.Error as e:
        die(e.code, str(e))
    finally:
        p, child = child, None
        if p.poll() is None:
            kill_group(p)
        p.wait()
    out, err = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    if err:
        sys.stderr.write(err if err.endswith("\n") else err + "\n")
        sys.stderr.flush()
    if "listen" not in cmd:                       # 子的回答原樣，不換字
        out = tool_words(out)
    if p.returncode == 0:
        return out, None
    lines = [x for x in err.splitlines() if x.strip()]
    mine = [m for m in map(err_re.match, lines) if m]
    if mine:
        code, reason = mine[-1].group(1), mine[-1].group(2)
        if code in TOOL_WORDS:                    # 下層那句在教 CLI 旗標：給腦的換成工具參數的寫法（只留分號前那段事實）
            reason = reason.split(";")[0] + "; " + TOOL_WORDS[code]
        return out, (code, tool_words(reason))
    return out, ("CommandFailed", "%s exited %d: %s" % (what, p.returncode, lines[-1] if lines else "(no message)"))


def must(cmd, **kw):
    out, err = run(cmd, **kw)
    if err:
        die(*err)
    return out


def agent(argv, **kw):
    """aos-agent argv…（daemon 照環境的 $AOS_DAEMON，cwd＝$AOS_WS）；錯＝die。"""
    return must(["aos-agent"] + list(argv), **kw)


def emit(out):
    sys.stdout.write(out if not out or out.endswith("\n") else out + "\n")


# ---- 查鍵 ----
def check_op(args, ops):
    """op 沒給＝ArgumentsBad、不認得＝OpUnknown、這個 op 不收的鍵＝ArgumentsBad；回 op。"""
    op = args.get("op")
    if op is None:
        die("ArgumentsBad", "op is required (%s)" % ", ".join(ops))
    if op not in ops:
        die("OpUnknown", "op must be one of %s (got %r)" % (", ".join(ops), op))
    extra = sorted(k for k in args if k != "op" and k not in ops[op])
    if extra:
        die("ArgumentsBad", "op %s does not take %s (it takes %s)" % (op, ", ".join(extra), ", ".join(ops[op]) or "nothing else"))
    return op


def text(args, key, need=False):
    v = args.get(key)
    if v is None and not need:
        return None
    if not isinstance(v, str) or not v:
        die("ArgumentsBad", "%s %s a non-empty string" % (key, "needs" if v is None else "must be"))
    return v


def flag(args, key):
    v = args.get(key, False)
    if not isinstance(v, bool):
        die("ArgumentsBad", "%s must be true or false" % key)
    return v


def seconds(args, key="timeout_s"):
    """有限正數秒；沒給＝None。"""
    v = args.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0 or not math.isfinite(v):
        die("ArgumentsBad", "%s must be a finite positive number of seconds" % key)
    return v


def cycles(args, key="timeout_cycles"):
    """正整數 cycle，加 30 個保險 cycle 後仍要放得進目前時鐘／間隔的 64-bit 範圍；沒給＝None。"""
    v = args.get(key)
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not 0 < v <= MAX_CYCLES:
        die("ArgumentsBad", "%s must be a positive integer at most %d" % (key, MAX_CYCLES))
    try:
        now = tool_io.now_cycle()
        interval = 1 if now is not None else tool_io.clock_interval_ms()
        now = tool_io.utc_now_epoch_ms() if now is None else now
    except tool_io.Error as e:
        die(e.code, str(e))
    if v > (9223372036854775807 - now) // interval - 30:
        die("ArgumentsBad", "%s plus 30 extra cycles exceeds the current clock/interval range" % key)
    return v


def guard(args):
    """等 daemon 的動作：子行程保險＝max(STEP_S, (timeout_s 或預設 30) + 30)。"""
    return max(STEP_S, (seconds(args) or CTL_DEFAULT_S) + 30)


def _timeout_flags(args, with_queued=False):
    s = seconds(args)
    out = ["--timeout-s", "%g" % s] if s is not None else []
    if with_queued and args.get("on_queued") is not None:
        if args["on_queued"] not in ("fail", "ok"):
            die("ArgumentsBad", "on_queued must be fail or ok")
        out += ["--on-queued", args["on_queued"]]
    return out


def _json_or_string(args, key):
    v = args[key]
    if isinstance(v, str) and v:
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, dict) and v:
        return json.dumps(v, ensure_ascii=False)
    die("ArgumentsBad", "%s must be a path string or a directive object like {\"$env\": \"AOS_HOME\", \"$path\": \"/templates/agent-fsm\"}" % key)


# ---- ctl add ----
def add_argv(args):
    """ctl add 的 argv（不含 aos-agent）：鍵一對一轉旗標；def 或 def_json 二選一，ws／ws_json、stack／stack_json 至多一個。"""
    if ("def" in args) == ("def_json" in args):
        die("ArgumentsBad", "add needs def (the definition folder) or def_json, not both")
    for a, b in (("ws", "ws_json"), ("stack", "stack_json")):
        if a in args and b in args:
            die("ArgumentsBad", "give %s or %s, not both" % (a, b))
    argv = ["ctl", "add"]
    name = text(args, "name")
    argv += ["--name", name] if name else []
    for key, opt in (("ws", "--ws"), ("stack", "--stack")):
        if key in args:
            argv += [opt, text(args, key, True)]
    for key, opt in (("ws_json", "--ws-json"), ("stack_json", "--stack-json"), ("def_json", "--path-json")):
        if key in args:
            argv += [opt, _json_or_string(args, key)]
    if "limits" in args:
        if not isinstance(args["limits"], dict):
            die("ArgumentsBad", "limits must be an object like {\"mem_mb\": 512}")
        argv += ["--limits", json.dumps(args["limits"], ensure_ascii=False)]
    envs = args.get("envs", {})
    if not isinstance(envs, dict) or not all(isinstance(k, str) and k and "=" not in k and isinstance(v, str) for k, v in envs.items()):
        die("ArgumentsBad", "envs must be an object of strings, like {\"LANG\": \"C\"}")
    argv += [x for k in sorted(envs) for x in ("--envs", "%s=%s" % (k, envs[k]))]
    argv += ["--auto-restart"] if flag(args, "auto_restart") else []
    argv += _timeout_flags(args, with_queued=True)
    if "def" in args:
        argv += [text(args, "def", True)]
    return argv


def make_ws(args):
    """ws 給了又不在＝先建（相對從 $AOS_WS 算；舊 agents 的行為）。"""
    ws = args.get("ws")
    if not isinstance(ws, str) or not ws:
        return
    path = ws if os.path.isabs(ws) else os.path.join(tool_io.workspace(), ws)
    if not os.path.isdir(path):
        try:
            os.makedirs(path)
        except OSError as e:
            die("MkdirFailed", "cannot create ws %s: %s" % (path, e))


def parse_added(out):
    """ctl add 的最後一行：子的 stack，或排隊中那行；回 {"stack": …} 或 {"queued_letter": …, "message": 那行}。"""
    line = out.strip().splitlines()[-1] if out.strip() else ""
    queued = QUEUED_RE.fullmatch(line)
    if queued:
        return {"queued_letter": queued.group(1), "message": line}
    return {"stack": line}


# ---- 帶目標的生滅停起 ----
def life_argv(op, args):
    """LIFE_OPS 的 op → ctl 的 argv（不含 aos-agent）。"""
    name = text(args, "name", True)
    if op == "rm":
        return ["ctl", "rm"] + (["--purge", "-y"] if flag(args, "purge") else []) + _timeout_flags(args) + [name]
    return ["ctl", op, "--target", name] + _timeout_flags(args, with_queued=op in ("start", "wake"))


def life_guard(op, args):
    return guard(args) if "timeout_s" in LIFE_OPS[op] else STEP_S
