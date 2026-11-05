# cli_session.py - 把 claude／codex 的一段對話接成工具：平常 agent 用非互動模式續同一個對話；人用 attach 接進互動畫面（tmux），跳出後畫面留著，agent 改從畫面送字
#
# 一個工具的小格（$AOS_STACK，act 給的是 $AOS_STACK/tools/<工具名>/，11-02 起）裡放：
#   session.txt   這段對話的 id（claude 的 session id／codex 的 thread id）；第一次講完話才有
#   tty.sock      tmux 的 socket：互動畫面活著時，CLI 的終端就接在這裡（attach＝tmux -S tty.sock attach）
#   tmux.conf     attach 開畫面時寫的 tmux 設定（Ctrl-] 或 Ctrl-\ 跳出、不用 prefix）
#   turns.jsonl   互動畫面每講完一輪，hook 接一行 {"answered_at", "text"}（answered_at＝講完的時間，10-25 前叫 at）（agent 從這裡拿回答，不去解析畫面）
#   busy.txt      claude 的畫面正在跑一輪（有人送出、還沒講完）
#   lock          同一時間只有一個人用這段對話（agent 的一次呼叫、attach 開畫面）
#   live.jsonl    非互動的即時紀錄兼副產物：claude 的 stream-json、codex 的 --json 事件，一行一事件、只接不重寫（10-28；10-27 是每次重寫）
#   tool.txt、ws.txt  這格屬於哪個工具資料夾、哪個工作區（open_cell 叫回畫面時用）（10-27）
#   stack.txt     給 aos-mcp 的 stack（11-03 eca-tools：平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；open_cell 叫回畫面時用）
#   mcp.json      claude 的 MCP 設定（11-03 eca-tools）：有登記檔才寫，每次起 claude 前重寫；codex 不寫檔、走 -c
#   transcripts/<kind>-<id>.jsonl  指到 CLI 自己存的這段對話的 symlink（claude ~/.claude/projects/*/<id>.jsonl、
#                 codex ~/.codex/sessions/**/*<id>.jsonl）：拿到 session id 就建（10-30 agent-lifecycle C-15～C-17；
#                 agent 叫的工具格也建，方向題 3）；一直是 symlink（11-02 晚 aos-eca 不再歸檔，freeze_transcripts 拿掉；
#                 CLI 會自己清舊對話，要留的人自己複製）
#
# 不再登記（10-30 eca 衝突 6）：10-28 起每用到一格就送一行 register 給 $AOS_HUB 的 aos-hub-kernel，現在刪了——
# 沒有 kernel，「只登記的實例」這個分類消失；工具叫的格是那隻 agent 的事（C-52），要看去看那隻 agent 自己的 stack。
#
# 兩條路（每次呼叫自己挑）：
#   畫面沒開 → 非互動：claude -p --resume <id>（第一次 --session-id <新 id>）、codex exec resume <id> -（第一次 codex exec -）
#   畫面開著 → 從 pty 送字：tmux paste-buffer 貼上＋Enter，等 hook 在 turns.jsonl 接一行（有人接著看、或 claude 正在跑一輪＝SessionBad；
#             on_busy="answer" 時不退讓：照樣貼、busy.txt 等它消失，10-31）
# 工具（11-03 eca-tools，thinking 2026-11-03-eca-tools）：cli.json 選填 tools＝aos-tools 的登記檔（相對路徑從 cli.json 的資料夾算），
#   沒寫＝cli.json 同層有 tools.json 就用它（使用者 11-03「如果cli.json沒有指定，那就去找默認的tools.json」）、沒有＝不接工具；
#   選填 tools_flags＝字串陣列，原樣插在 aos-mcp 的 args 裡（例 ["--enable-logs"]）。有登記檔時每次起 CLI 前接上
#   aos-mcp --ws <工作區> --stack <stack> [tools_flags…] <登記檔絕對路徑>：claude＝寫小格 mcp.json、加 --mcp-config 它 --allowedTools mcp__aos；
#   codex＝兩個 -c mcp_servers.aos.command／args。aos-mcp 靠 PATH 找（N-50）；定義資料夾一個字都不寫（P-15）。
#   $AOS_STACK 裡這隻自己的（aos-agent tools／llm 寫的，stack_copies）：tools.json＝覆蓋層（11-05 起只存差異；cli.json 沒明寫 tools 時
#   給 aos-mcp --overlay，疊在定義的登記檔上，定義那份不在也行）、llm.json 的 model。
#   模型（11-04 晚 think-as-function 03 § 2）：cli.json 同層的 llm.json（定義）疊 $AOS_STACK/llm.json（副本）的 model＝flags 的 --model（換掉或加在尾）；都沒有＝flags 原樣。
# 開場白不歸這層（11-04 翻案，使用者「不該在json中指定檔案名稱，應該改成用旗標指定」）：是 aos-eca-turn 的 --prompt FILE；
#   cli.json 寫了 prompt 跟其他沒認的鍵一樣不看。
# 錯：當工具叫（call_main）時照 lib 契約 stderr 與 stdout 各一行「工具名: 代號 原因」、退 1；attach 與 hook 是 stderr 一行「cli_session: 代號 原因」、退 1。
#
# 放哪（10-24 遷移）：proto8/lib/agent/cli_session.py，lib/agent 的 claude、codex 兩個工具共用（用 realpath 找到這層再 import）；
# 掛它的 agent 根目錄可以放一份 cli_session.py（或捷徑）給 attach 用（原本的例子 demo/agent-fay 11-03 晚刪了）。工具資料夾（cli.json 在裡面）由工具入口傳進來、
# agent 資料夾（attach 列 tools/）由 attach 傳進來——這支不再假設自己放在哪隻 agent 底下。
import datetime, fcntl, glob, json, os, shlex, shutil, subprocess, sys, threading, time, uuid

TMUX_SESSION = "cli"
PROG, ECHO = "cli_session", False                    # 錯誤行開頭、要不要也印到 stdout（call_main 改成工具名、True）


def die(code, reason):
    line = "%s: %s %s" % (PROG, code, str(reason).replace("\n", " "))
    print(line, file=sys.stderr)
    if ECHO:
        print(line)                                  # 當工具叫時 stdout 也印：stdout 是給腦看的結果
    sys.exit(1)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def load_cfg(tool_dir):
    path = os.path.join(tool_dir, "cli.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        die("CfgMissing", path)
    except (OSError, ValueError) as e:
        die("CfgBad", "%s: %s" % (path, e))
    if not isinstance(cfg, dict) or cfg.get("kind") not in ("claude", "codex"):
        die("CfgBad", "%s: kind must be claude or codex" % path)
    for k in ("flags", "print_flags", "tools_flags"):
        if not isinstance(cfg.get(k, []), list) or not all(isinstance(a, str) for a in cfg.get(k, [])):
            die("CfgBad", "%s: %s must be an array of strings" % (path, k))
    cfg["registry"] = registry(cfg, tool_dir, path)
    stack_copies(cfg, tool_dir)
    return cfg


def read_llm(path):
    """llm.json：一層物件；不在＝{}。"""
    try:
        with open(path, encoding="utf-8") as f:
            llm = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        die("CfgBad", "%s: %s" % (path, e))
    if not isinstance(llm, dict):
        die("CfgBad", "%s: must be a flat object" % path)
    return llm


def stack_copies(cfg, tool_dir):
    """子介面 tools（11-05 portable-flow 步 4，使用者「tools只存差異」）：$AOS_STACK/tools.json 在、cli.json 又沒明寫 tools＝它是這隻的覆蓋層，
    cfg["overlay"]＝它、交給 aos-mcp --overlay（疊法歸 aos-tools）；定義沒有登記檔＝registry 用同層 tools.json 的路徑（不在也行）。
    腦設定（11-04 晚 think-as-function 03 § 2）：cli.json 同層的 llm.json（定義）疊 $AOS_STACK/llm.json（副本，aos-agent llm set 寫的）；
    有 model＝flags 的 --model 換成它（沒有就加在尾）。每次 load_cfg（每題）重讀＝下一題生效。"""
    stack = os.environ.get("AOS_STACK")
    llm = read_llm(os.path.join(tool_dir, "llm.json"))
    if stack:
        copy = os.path.join(stack, "tools.json")
        if "tools" not in cfg and os.path.isfile(copy):
            cfg["overlay"] = copy
            if not cfg.get("registry"):
                cfg["registry"] = os.path.join(os.path.abspath(tool_dir), "tools.json")
        llm.update(read_llm(os.path.join(stack, "llm.json")))
    model = llm.get("model")
    if "model" in llm and (not isinstance(model, str) or not model):
        die("CfgBad", "model in llm.json must be a non-empty string (same as agent-fsm's brain.py), not %s" % json.dumps(model))
    if model:
        flags = list(cfg.get("flags", []))
        if "--model" in flags[:-1]:
            flags[flags.index("--model") + 1] = model
        else:
            flags += ["--model", model]
        cfg["flags"] = flags


def registry(cfg, tool_dir, path):
    """這份定義的 aos-tools 登記檔（絕對路徑）；沒有＝None（11-03 eca-tools）。
    tools 有寫＝它（相對路徑從 cli.json 的資料夾算），不是檔＝ToolsMissing；沒寫＝同層 tools.json，有才用。
    給了 tools_flags 卻沒有登記檔＝CfgBad（寫什麼就做什麼，不靜靜吞掉）。"""
    base = os.path.abspath(tool_dir)
    if "tools" in cfg:
        if not isinstance(cfg["tools"], str) or not cfg["tools"]:
            die("CfgBad", "%s: tools must be the path of a registry file (a non-empty string)" % path)
        reg = os.path.normpath(os.path.join(base, cfg["tools"]))
        if not os.path.isfile(reg):
            die("ToolsMissing", "%s: registry file named by tools not found: %s" % (path, reg))
        return reg
    reg = os.path.join(base, "tools.json")
    if os.path.isfile(reg):
        return reg
    if "tools_flags" in cfg:
        die("CfgBad", "%s: tools_flags given but no registry file (no tools, and no tools.json alongside)" % path)
    return None


def mcp_argv(cfg, cell, ws, stack):
    """有登記檔＝接上 aos-mcp 要加給 CLI 的旗標；沒有＝[]（11-03 eca-tools）。每次起 CLI 前叫（claude 的 mcp.json 每次重寫）。
    ws＝CLI 的 cwd、stack＝給 aos-mcp 的 --stack（工具叫的小格在 <stack>/tools/<名>/）。"""
    reg = cfg.get("registry")
    if not reg:
        return []
    if not os.path.isfile(reg) and not cfg.get("overlay"):   # load_cfg 之後才被刪掉（有覆蓋層時定義那份可以不在）
        die("ToolsMissing", "registry file not found: %s" % reg)
    if shutil.which("aos-mcp") is None:
        die("CliMissing", "aos-mcp is not on PATH (tools are attached; add proto8/extras/ai_tools/bin to PATH)")
    args = ["--ws", ws, "--stack", stack] + cfg.get("tools_flags", []) + (["--overlay", cfg["overlay"]] if cfg.get("overlay") else []) + [reg]
    if cfg["kind"] == "codex":                           # JSON 字串與字串陣列同時是合法的 TOML（-c 的值照 TOML 解）
        return ["-c", "mcp_servers.aos.command=" + json.dumps("aos-mcp"), "-c", "mcp_servers.aos.args=" + json.dumps(args)]
    try:
        cell.write("mcp.json", json.dumps({"mcpServers": {"aos": {"command": "aos-mcp", "args": args}}},
                                          ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot write %s: %s" % (cell.file("mcp.json"), e))
    return ["--mcp-config", cell.file("mcp.json"), "--allowedTools", "mcp__aos"]


class Cell:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        os.makedirs(self.path, exist_ok=True)

    def file(self, name):
        return os.path.join(self.path, name)

    def read(self, name):
        try:
            with open(self.file(name), encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def write(self, name, text):                     # N-05：先寫 . 開頭的暫存檔再改名
        tmp = self.file("." + name)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, self.file(name))

    def turns(self):
        try:
            with open(self.file("turns.jsonl"), encoding="utf-8") as f:
                return [json.loads(l) for l in f if l.strip()]
        except FileNotFoundError:
            return []

    def lock(self):
        f = open(self.file("lock"), "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return f, False
        return f, True

    def tmux(self, *args, **kw):
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        return subprocess.run(["tmux", "-S", self.file("tty.sock")] + list(args), **kw)

    def alive(self):
        if not os.path.exists(self.file("tty.sock")):
            return False
        try:
            return self.tmux("has-session", "-t", TMUX_SESSION).returncode == 0
        except FileNotFoundError:            # 沒有 tmux：畫面不可能開著
            return False

    def clients(self):
        r = self.tmux("list-clients", "-t", TMUX_SESSION, "-F", "#{client_tty}")
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def note_cell(cell, tool_dir, ws, stack):
    """記下這格是哪個工具、哪個工作區、哪個 stack（tool.txt、ws.txt、stack.txt〔11-03 eca-tools〕；open_cell 叫回畫面要）。寫不成不擋正事。
    10-30 前叫 register，還會送一行給 $AOS_HUB 的 kernel；那段刪了（eca 衝突 6）。"""
    try:
        for name, value in (("tool.txt", tool_dir), ("ws.txt", ws), ("stack.txt", stack)):
            if cell.read(name) != value:
                cell.write(name, value + "\n")
    except OSError:
        pass


def close(cell):
    """關掉畫面（tmux 和裡面的 CLI；對話是 CLI 邊講邊存的，id 留在 session.txt）。回 True＝本來開著。"""
    if not cell.alive():
        return False
    cell.tmux("kill-server")
    return True


def transcripts(kind, sid):
    """CLI 自己存的這段對話（含中間訊息、工具呼叫等副產物）放在哪：claude ~/.claude/projects/*/<id>.jsonl、
    codex ~/.codex/sessions/年/月/日/rollout-*-<id>.jsonl。小格的 transcripts/ symlink 指到這裡（10-30；10-28 是 stop 時才拷）。"""
    if not sid:
        return []
    if kind == "claude":
        base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
        return sorted(glob.glob(os.path.join(base, "projects", "*", sid + ".jsonl")))
    base = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    return sorted(glob.glob(os.path.join(base, "sessions", "**", "*%s.jsonl" % sid), recursive=True))


def transcript_link(cell_path, kind, sid):
    """小格裡指到 CLI 自己那份對話的 symlink 放哪：transcripts/<kind>-<id>.jsonl（10-30）。"""
    return os.path.join(cell_path, "transcripts", "%s-%s.jsonl" % (kind, sid))


def link_transcript(cell, kind):
    """拿到 session id 就在小格建 symlink 指到 CLI 自己的對話檔（10-30 C-16、C-17）。已有就不動；
    找不到（CLI 還沒寫、--no-session-persistence）就不建；任何問題都不擋正事。"""
    sid = cell.read("session.txt")
    if not sid:
        return
    link = transcript_link(cell.path, kind, sid)
    try:
        if os.path.lexists(link):
            return
        found = transcripts(kind, sid)
        if not found:
            return
        os.makedirs(os.path.dirname(link), exist_ok=True)
        tmp = os.path.join(os.path.dirname(link), "." + os.path.basename(link) + ".tmp")   # N-05：先建暫存再改名
        if os.path.lexists(tmp):
            os.remove(tmp)
        os.symlink(os.path.abspath(found[0]), tmp)
        os.replace(tmp, link)
    except OSError:
        pass


# ---------------------------------------------------------------- 非互動（畫面沒開）

def run_cli(argv, prompt, ws, timeout_ms, handed=None):
    """起 CLI、題目從 stdin 給、等它做完；起來了就叫 handed（交出去了，11-03 aos-eca-turn 在這一刻收信）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, cwd=ws)
    except FileNotFoundError:
        die("CliMissing", "%s is not on PATH" % argv[0])
    if handed:
        handed()
    try:
        out, err = p.communicate(prompt, timeout=timeout_ms / 1000)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return subprocess.CompletedProcess(argv, p.returncode, out, err)


def tail(text, n=300):
    return (text or "").strip()[-n:]


def run_claude_stream(argv, prompt, ws, timeout_ms, live_path, handed=None):
    """claude -p --output-format stream-json：每行一邊寫進 live.jsonl（人可以 tail 著看），一邊收起來；回 (結束碼, 全部行, stderr)。
    題目寫進 stdin、關掉之後叫 handed（交出去了，11-03）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, cwd=ws)
    except FileNotFoundError:
        die("CliMissing", "%s is not on PATH" % argv[0])
    p.stdin.write(prompt)
    p.stdin.close()
    if handed:
        handed()
    deadline, lines = time.time() + timeout_ms / 1000, []
    err = []
    t = threading.Thread(target=lambda: err.append(p.stderr.read()), daemon=True)
    t.start()
    timer = threading.Timer(timeout_ms / 1000, p.kill)
    timer.start()
    try:
        with open(live_path, "a", encoding="utf-8") as live:      # 10-28：只接不重寫（副產物留著）
            for line in p.stdout:
                lines.append(line)
                live.write(line)
                live.flush()
        p.wait()
    finally:
        timer.cancel()
    t.join(1)
    if time.time() > deadline:
        die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return p.returncode, lines, "".join(err)


def print_claude(cfg, cell, ws, stack, prompt, handed=None):
    sid = cell.read("session.txt")
    new = "" if sid else str(uuid.uuid4())
    # 10-27：改 stream-json（--verbose 是它要的），一行一事件寫進小格的 live.jsonl，人用 aos-agent watch 看得到它正在做什麼；
    # 回答取最後一個帶 result 的那行（type: result）
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"] + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += mcp_argv(cfg, cell, ws, stack)
    argv += ["--resume", sid] if sid else ["--session-id", new]
    code, lines, err = run_claude_stream(argv, prompt, ws, cfg.get("timeout_ms", 600000), cell.file("live.jsonl"), handed)
    out = None
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and "result" in ev:
            out = ev
    stdout = "".join(lines)
    if out is None:
        die("CliFailed", "claude exited %d with no result in its output: %s %s" % (code, tail(stdout), tail(err)))
    if code != 0 or out.get("is_error"):   # result 行自己帶原因（例 模型不存在）就印它；stdout 尾巴會切在 JSON 中間
        why = out.get("result") if isinstance(out.get("result"), str) and out.get("result") else tail(stdout)
        die("CliFailed", "claude exited %d: %s %s" % (code, tail(why), tail(err)))
    if not sid:
        cell.write("session.txt", (out.get("session_id") or new) + "\n")
    return out.get("result") or ""


def print_codex(cfg, cell, ws, stack, prompt, handed=None):
    sid = cell.read("session.txt")
    last = cell.file("last.txt")
    argv = ["codex", "exec"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += mcp_argv(cfg, cell, ws, stack)
    argv += ["--skip-git-repo-check", "--json", "-o", last, "-"]     # 題目從 stdin 進（"-"）
    if os.path.exists(last):
        os.remove(last)
    r = run_cli(argv, prompt, ws, cfg.get("timeout_ms", 600000), handed)
    try:                                         # 10-28：--json 的事件（中間訊息、跑過的指令）也接進 live.jsonl 留著
        with open(cell.file("live.jsonl"), "a", encoding="utf-8") as live:
            live.write(r.stdout if not r.stdout or r.stdout.endswith("\n") else r.stdout + "\n")
    except OSError:
        pass
    thread = ""
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "thread.started":
            thread = ev.get("thread_id") or thread
    if r.returncode != 0 or not os.path.exists(last):
        die("CliFailed", "codex exited %d: %s" % (r.returncode, tail(r.stderr) or tail(r.stdout)))
    if not sid and thread:
        cell.write("session.txt", thread + "\n")
    with open(last, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 從畫面送字（畫面開著）

def live(cfg, cell, prompt, on_busy="yield", handed=None):
    """on_busy＝yield（預設）：有人接在畫面上、或 busy.txt 在＝SessionBad；answer（10-31 eca --on-busy）：有人接著照樣貼，
    busy.txt 在就等它消失再貼——等它跟等回答共用 timeout_ms 的期限，逾時 ReplyMissing。貼上、按 Enter 之後叫 handed（交出去了，11-03）。"""
    deadline = time.time() + cfg.get("timeout_ms", 600000) / 1000
    if on_busy == "yield":
        who = cell.clients()
        if who:
            die("SessionBad", "someone is attached to the screen (%s); call again after they detach" % ", ".join(who))
        if os.path.exists(cell.file("busy.txt")):
            die("SessionBad", "a turn is running on the screen (sent, not finished yet); call again after it finishes")
    while os.path.exists(cell.file("busy.txt")) and time.time() < deadline:
        if not cell.alive():
            die("CliFailed", "the screen closed before the turn finished")
        time.sleep(0.2)
    if os.path.exists(cell.file("busy.txt")):                # 等到期限還在跑：不貼，免得逾時了還打進畫面
        die("ReplyMissing", "the turn on the screen did not finish within %d s; not sent (attach to look)" % (cfg.get("timeout_ms", 600000) // 1000))
    seen = len(cell.turns())
    r = cell.tmux("load-buffer", "-b", "aos", "-", input=prompt)
    if r.returncode != 0:
        die("CliFailed", "tmux load-buffer: %s" % tail(r.stderr))
    cell.tmux("paste-buffer", "-p", "-d", "-b", "aos", "-t", TMUX_SESSION)   # -p：程式要的話包成 bracketed paste，多行不會半路送出
    time.sleep(0.3)
    cell.tmux("send-keys", "-t", TMUX_SESSION, "Enter")
    if handed:
        handed()
    while time.time() < deadline:
        turns = cell.turns()
        if len(turns) > seen:
            return turns[-1].get("text") or ""
        if not cell.alive():
            die("CliFailed", "the screen closed before the turn finished")
        time.sleep(0.2)
    die("ReplyMissing", "no answer %d s after sending (may be stuck on a permission or trust prompt; attach to look)"
        % (cfg.get("timeout_ms", 600000) // 1000))


def ask(cfg, cell, tool_dir, ws, stack, prompt, on_busy="yield", handed=None):
    """問 CLI 一句 → 回答文字：記下這格（note_cell）→ 拿格的 lock（拿不到：on_busy＝yield（預設）＝SessionBad、
    answer＝等到拿到，同 open_cell）→ 畫面開著走 live（on_busy 照傳）、沒開走非互動
    → 建 transcripts symlink。工具形（call_main）與 aos-eca-turn 共用這一段（10-30 eca 第 5 步抽出來）。
    tool_dir＝cli.json 所在的資料夾（工具資料夾或 eca 定義）；ws＝CLI 的 cwd（絕對路徑）；stack＝給 aos-mcp 的 --stack
    （平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；11-03 eca-tools）。handed＝選填、不帶參數的函式：題目交給 CLI 的那一刻叫一次
    （非互動＝CLI 起來、題目寫進去；畫面＝貼上按 Enter），在等回答之前（11-03 aos-eca-turn 在這一刻收信；工具形不給）。錯一律走 die
    （工具形印一行退 1；aos-eca-turn 把 die 換成丟例外）。"""
    note_cell(cell, tool_dir, ws, stack)
    f, ok = cell.lock()
    if not ok:
        if on_busy == "yield":
            die("SessionBad", "this conversation is in use (another call, or attach is opening the screen)")
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        if cell.alive():
            text = live(cfg, cell, prompt, on_busy, handed)
        elif cfg["kind"] == "claude":
            text = print_claude(cfg, cell, ws, stack, prompt, handed)
        else:
            text = print_codex(cfg, cell, ws, stack, prompt, handed)
        link_transcript(cell, cfg["kind"])               # 工具形也留（方向題 3）
    return text


def call_main(tool_dir, on_busy="yield"):
    """工具入口：stdin {"prompt": "..."} → stdout 回答。tool_dir＝工具資料夾（cli.json 在裡面；名字＝資料夾名）。
    on_busy 照傳給 ask（lib/agent/claude、codex 用預設 yield；aos-eca-turn --one 照它的 --on-busy）。"""
    global PROG, ECHO
    PROG, ECHO = os.path.basename(tool_dir), True
    cfg = load_cfg(tool_dir)
    stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS", ".")
    if not stack:
        die("StackMissing", "AOS_STACK is not set")
    try:
        args = json.loads(sys.stdin.read())
    except ValueError as e:
        die("ArgumentsBad", "stdin is not JSON: %s" % e)
    if not isinstance(args, dict) or not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        die("ArgumentsBad", "missing prompt (a non-empty string)")
    cell = Cell(stack)                                   # 工具形：對話在這格本身，aos-mcp 的 stack 也是它（它叫的工具再疊 tools/<名>/）
    text = ask(cfg, cell, os.path.abspath(tool_dir), os.path.abspath(ws), cell.path, args["prompt"], on_busy)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


# ---------------------------------------------------------------- hook（互動畫面講完一輪時 CLI 叫的）

def last_text_from_transcript(path):
    """claude 的 transcript（jsonl）裡最後一則 assistant 的文字。"""
    text = ""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if m.get("type") != "assistant":
                    continue
                content = (m.get("message") or {}).get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
                    if parts:
                        text = "".join(parts)
    except OSError:
        pass
    return text


def hook_main(kind, cell_path, payload_arg=None):
    """claude：stdin 一份 hook JSON（UserPromptSubmit／Stop）；codex：notify 把 JSON 放在最後一個參數。
    hook 不准讓 CLI 出錯：任何問題都吞掉、退 0。"""
    try:
        cell = Cell(cell_path)
        raw = payload_arg if kind == "codex" else sys.stdin.read()
        p = json.loads(raw)
        if kind == "claude":
            if p.get("hook_event_name") == "UserPromptSubmit":
                cell.write("busy.txt", now() + "\n")
                return
            if p.get("hook_event_name") != "Stop":
                return
            text = p.get("last_assistant_message")
            if not isinstance(text, str):
                text = last_text_from_transcript(p.get("transcript_path") or "")
            sid = p.get("session_id")
        else:
            if p.get("type") != "agent-turn-complete":
                return
            text = p.get("last-assistant-message") or ""
            sid = p.get("thread-id") or p.get("thread_id")
        if sid and not cell.read("session.txt"):
            cell.write("session.txt", sid + "\n")
        link_transcript(cell, kind)
        with open(cell.file("turns.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"answered_at": now(), "text": text}, ensure_ascii=False) + "\n")
        if os.path.exists(cell.file("busy.txt")):
            os.remove(cell.file("busy.txt"))
    except Exception:            # noqa: BLE001 —— hook 壞了也不能卡住 CLI
        pass


# ---------------------------------------------------------------- 開畫面（attach 用）

TMUX_CONF = """# tmux.conf - tmux settings for the screen attach opens (cli_session.py rewrites it each time)
set -g prefix None
unbind-key C-b
bind-key -n 'C-\\' detach-client
bind-key -n 'C-]' detach-client
set -g escape-time 0
set -g focus-events on
set -g status-left ''
set -g status-right ' Ctrl-] detach (the screen stays) | /exit or /quit inside to end '
set -g status-right-length 80
"""


def hook_cmd(kind, cell):
    return [sys.executable, os.path.abspath(__file__), "hook", kind, cell.path]


def start(cfg, cell, ws, stack):
    """畫面沒開就開一個（在 tmux 裡、背景）；有對話就接著那段，沒有就開新的。有登記檔＝跟非互動同一段接上 aos-mcp（11-03 eca-tools）。"""
    if cell.alive():
        return False
    sid = cell.read("session.txt")
    link_transcript(cell, cfg["kind"])                   # 叫回舊對話：id 早就知道
    if cfg["kind"] == "claude":
        cmd = " ".join(shlex.quote(a) for a in hook_cmd("claude", cell))
        hooks = {"hooks": {e: [{"hooks": [{"type": "command", "command": cmd}]}]
                           for e in ("UserPromptSubmit", "Stop")}}
        argv = ["claude"] + cfg.get("flags", []) + mcp_argv(cfg, cell, ws, stack) + ["--settings", json.dumps(hooks)]
        argv += ["--resume", sid] if sid else []
    else:
        argv = ["codex"] + (["resume", sid] if sid else []) + cfg.get("flags", []) + mcp_argv(cfg, cell, ws, stack)
        argv += ["-c", "notify=" + json.dumps(hook_cmd("codex", cell))]
    with open(cell.file("tmux.conf"), "w", encoding="utf-8") as f:
        f.write(TMUX_CONF)
    for name in ("busy.txt",):
        if os.path.exists(cell.file(name)):
            os.remove(cell.file(name))
    try:
        r = cell.tmux("-f", cell.file("tmux.conf"), "new-session", "-d", "-s", TMUX_SESSION,
                      "-x", "160", "-y", "45", "-c", ws, "--", *argv)
    except FileNotFoundError:
        die("TmuxMissing", "tmux is not on PATH")
    if r.returncode != 0:
        die("CliFailed", "tmux new-session: %s" % tail(r.stderr))
    # 等畫面穩下來（CLI 開機要幾秒；太早貼字會被吃掉）：畫面有字、連續 3 秒沒變、不是停在「Resuming session…」
    # （10-24 實跑：codex 的「Resuming session…」會停 2 秒以上不動，1.5 秒的門檻會太早放行）
    last, stable_since, deadline = None, time.time(), time.time() + 30
    while time.time() < deadline and cell.alive():
        screen = cell.tmux("capture-pane", "-p", "-t", TMUX_SESSION).stdout
        if screen != last:
            last, stable_since = screen, time.time()
        elif screen.strip() and "Resuming session" not in screen and time.time() - stable_since > 3:
            break
        time.sleep(0.25)
    if not cell.alive():
        die("CliFailed", "%s exited right after starting (wrong session id?)" % argv[0])
    return True


ATTACH_USAGE = """usage: attach [--ws WS] [-d] [TOOL]
  Attach to TOOL's interactive screen, opening it first if needed.
  -d     open only, do not attach
  no TOOL: list each tool's screen state"""


def attach_main(argv, agent_dir):
    """attach [--ws WS] [-d] [工具名]：接進那個工具的互動畫面；沒開就先開。-d＝只開、不接。沒給工具名＝列出各工具的狀態。"""
    ws, detached, names = os.environ.get("AOS_WS") or ".", False, []
    it = iter(argv)
    for a in it:
        if a == "--ws":
            ws = next(it, None) or die("ArgumentsBad", "--ws needs a path")
        elif a.startswith("--ws="):
            ws = a[5:]
        elif a == "-d":
            detached = True
        elif a in ("-h", "--help"):
            print(ATTACH_USAGE)
            return
        elif a.startswith("-"):
            die("FlagUnknown", a)
        else:
            names.append(a)
    ws = os.path.abspath(ws)
    if not os.path.isdir(ws):
        die("WsMissing", ws)
    stack = os.environ.get("AOS_STACK") or os.path.join(ws, ".stack")
    tools_dir = os.path.join(agent_dir, "tools")
    known = sorted(t for t in os.listdir(tools_dir) if os.path.isfile(os.path.join(tools_dir, t, "cli.json")))
    if not names:
        for t in known:
            cell = Cell(os.path.join(stack, "tools", t))
            state = "screen open" if cell.alive() else "screen closed"
            if cell.alive() and cell.clients():
                state += ", attached"
            print("%-8s %s | session %s | %s" % (t, state, cell.read("session.txt") or "(none yet)", cell.path))
        return
    if len(names) > 1:
        die("ArgumentsBad", "attach one tool at a time")
    if names[0] not in known:
        die("ToolUnknown", "%s (known: %s)" % (names[0], ", ".join(known)))
    cell = Cell(os.path.join(stack, "tools", names[0]))
    note_cell(cell, os.path.realpath(os.path.join(tools_dir, names[0])), ws, cell.path)   # 工具形：stack＝這格（同 call_main）
    opened = open_cell(cell)
    if detached:
        print("%s screen %s: %s" % (names[0], "opened" if opened else "already open", cell.file("tty.sock")))
        return
    print("attaching to %s (Ctrl-\\ detaches, the screen stays; /exit inside to end)" % names[0], file=sys.stderr)
    os.execvp("tmux", ["tmux", "-S", cell.file("tty.sock"), "attach", "-t", TMUX_SESSION])


def open_cell(cell):
    """畫面沒開就開（有 session.txt 就 --resume 接回那段＝叫回）；工具、工作區、stack 照格裡的 tool.txt、ws.txt、stack.txt。回 True＝這次才開的。
    stack.txt 只在接了工具時要（沒有＝CellBad；11-03 eca-tools）。"""
    tool_dir, ws, stack = cell.read("tool.txt"), cell.read("ws.txt"), cell.read("stack.txt")
    if not tool_dir or not ws:
        die("CellBad", "%s has no tool.txt/ws.txt (not a cell cli_session has used)" % cell.path)
    cfg = load_cfg(tool_dir)
    if cfg.get("registry") and not stack:
        die("CellBad", "%s has no stack.txt (tools are attached; need the stack for aos-mcp)" % cell.path)
    f, ok = cell.lock()
    if not ok:
        print("the agent is using this conversation; waiting for its turn to finish...", file=sys.stderr)
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        return start(cfg, cell, ws, stack)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "hook":
        hook_main(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        die("ArgumentsBad", "usage: cli_session.py hook <claude|codex> <cell> [payload] (tool entries and attach import it)")
