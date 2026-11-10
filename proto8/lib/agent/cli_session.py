# cli_session.py - 把 claude／codex 的一段對話接成工具：平常 agent 用非互動模式續同一個對話；人用 attach 接進互動畫面（tmux），跳出後畫面留著，agent 改從畫面送字
#
# 一個工具的小格（$AOS_STACK，act 給的是 $AOS_STACK/tools/<工具名>/，11-02 起）裡放：
#   session.txt   這段對話的 id（claude 的 session id／codex 的 thread id）：claude 新對話在交出去那一刻就寫（id 是我們產的）；
#                 codex 新對話讀到輸出的 thread.started 就寫（成敗都寫）；畫面那條路是 hook 收到第一輪時寫（11-10 two-machines 05）
#   .session_home 記號檔（不進 git）：{"session", "ws", "home", "machine"}——這段對話是在哪台機器（machine_id()）、哪個工作區（realpath）、
#                 哪個帳號資料夾（claude：CLAUDE_CONFIG_DIR 或 ~/.claude；codex：CODEX_HOME 或 ~/.codex）開的；跟 session.txt 一起寫、一起刪
#                 （machine 是 11-10 TS 8 加的：cp -a 時記號檔會跟過去；舊記號檔沒有這個 key＝不比機器）
#   （畫面的 tmux socket 不在小格裡，11-10 TS 10：/mnt/c 上 AF_UNIX bind 不了）實際放 ${XDG_RUNTIME_DIR:-/tmp}/aos-tty-<uid>/<小格 realpath
#                 sha256 前 16 hex>.sock（資料夾 0700），路徑只由 tty_socket() 算（attach＝tmux -S "$(那條)" attach）；小格搬了＝雜湊不同＝
#                 畫面當作沒開（本來就是死的）。11-10 以前開的畫面 socket 在小格的 tty.sock：還找得到就照用（過渡），不再新建
#   tmux.conf     attach 開畫面時寫的 tmux 設定（Ctrl-] 或 Ctrl-\ 跳出、不用 prefix）
#   turns.jsonl   互動畫面每講完一輪，hook 接一行 {"answered_at", "text"}（answered_at＝講完的時間，10-25 前叫 at）（agent 從這裡拿回答，不去解析畫面）
#   busy.txt      claude 的畫面正在跑一輪（有人送出、還沒講完）
#   lock          同一時間只有一個人用這段對話（agent 的一次呼叫、attach 開畫面）
#   live.jsonl    非互動的即時紀錄兼副產物：claude 的 stream-json、codex 的 --json 事件，一行一事件、只接不重寫（10-28；10-27 是每次重寫）
#   tool.txt、ws.txt  這格屬於哪個工具資料夾、哪個工作區（相對小格；open_cell 叫回畫面時用）
#   stack.txt     給 aos-mcp 的 stack（相對小格；平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；open_cell 叫回畫面時用）
#   mcp.json      claude 的 MCP 設定（11-03 eca-tools）：有登記檔才寫，每次起 claude 前重寫；codex 不寫檔、走 -c
#   transcripts/<kind>-<id>.jsonl  指到 CLI 自己存的這段對話的 symlink（claude ~/.claude/projects/*/<id>.jsonl、
#                 codex ~/.codex/sessions/**/*<id>.jsonl）：拿到 session id 就建（10-30 agent-lifecycle C-15～C-17；
#                 agent 叫的工具格也建，方向題 3）；一直是 symlink（11-02 晚 aos-eca 不再歸檔，freeze_transcripts 拿掉；
#                 CLI 會自己清舊對話，要留的人自己複製）
#
# 兩條路（每次呼叫自己挑）：
#   畫面沒開 → 非互動：claude -p --resume <id>（第一次 --session-id <新 id>）、codex exec resume <id> -（第一次 codex exec -）
#   畫面開著 → 從 pty 送字：tmux paste-buffer 貼上＋Enter，等 hook 在 turns.jsonl 接一行（有人接著看、或 claude 正在跑一輪＝SessionBad；
#             claude 停在信任資料夾選單＝TrustMissing、不貼，11-10 深夜；
#             on_busy="answer" 時不退讓：照樣貼、busy.txt 等它消失，10-31）
# 工具（11-03 eca-tools，thinking 2026-11-03-eca-tools）：cli.json 選填 tools＝aos-tools 的登記檔（相對路徑從 cli.json 的資料夾算；
#   也可寫指示詞，例 {"$env": "AOS_HOME", "$path": "/lib/x/tools.json"}，每次讀才解、不寫回，11-10 two-machines TC），
#   沒寫＝cli.json 同層有 tools.json 就用它（使用者 11-03「如果cli.json沒有指定，那就去找默認的tools.json」）、沒有＝不接工具；
#   選填 tools_flags＝字串陣列，原樣插在 aos-mcp 的 args 裡（例 ["--enable-logs"]）。定義的 interfaces.json 宣告了 hooks＝再加 --hooks <定義>
#   （11-10 hook：before_tool／after_tool 在 aos-mcp 跑）。有登記檔時每次起 CLI 前接上
#   aos-mcp --ws <工作區> --stack <stack> [tools_flags…] <登記檔絕對路徑>：claude＝寫小格 mcp.json、加 --mcp-config 它 --allowedTools mcp__aos；
#   codex＝兩個 -c mcp_servers.aos.command／args。aos-mcp 靠 PATH 找（N-50）；定義資料夾一個字都不寫（P-15）。
#   $AOS_STACK 裡這隻自己的（aos-agent tools／llm 寫的，stack_copies）：tools.json＝這隻自己那份（只存差異、"$override" 指回定義那份，
#   11-10 aos-tools-cli；cli.json 沒明寫 tools 時在就把它給 aos-mcp，疊法歸 aos-tools）、llm.json 的 model。
#   模型（11-04 晚 think-as-function 03 § 2）：cli.json 同層的 llm.json（定義）疊 $AOS_STACK/llm.json（副本）的 model＝flags 的 --model（換掉或加在尾）；都沒有＝flags 原樣。
# 換台（11-10 two-machines 05）：要接舊對話前先認「是不是這台的」（session_here：記號檔的 session、home 一樣，claude 再比 ws；
#   不讀 CLI 的任何檔內容、不靠它的錯誤訊息）。不是＝在交出去之前改開新對話：呼叫者給了 reseed（aos-eca-turn）＝把 reseed(上限)
#   整理過的紀錄接在題目前面（上限＝cli.json 選填 reseed_bytes，預設 48000；畫面那條路取 min(它, 8000)）；沒給（工具形）＝stderr
#   一行 warning、照樣開新的。記號檔不在但 transcripts() 找得到＝功能上線前就在跑的，當這台的、補寫記號檔（過渡補丁）。
#   以為是這台的、resume 卻失敗而且 transcripts() 找不到那個 id＝刪 session.txt 與 .session_home 再報錯（那封掉了，下一封開新的）。
#   新對話第一輪就失敗、而 transcripts() 找不到這次的新 id（CLI 沒建出對話）＝同樣刪兩個檔（11-10 TS 9，T3 缺口 1）：
#   下一輪直接開新的，不再拿一封去 --resume 一個不存在的對話。畫面那條路沒這個情況（session.txt 由 hook 在一輪講完才寫）。
#   畫面（start）：session.txt 在但不是這台的＝刪兩個檔、不帶 --resume 開新的。人想重開＝手刪 session.txt（正式用法）。
# 開場白不歸這層（11-04 翻案，使用者「不該在json中指定檔案名稱，應該改成用旗標指定」）：是 aos-eca-turn 的 --prompt FILE；
#   cli.json 寫了 prompt 跟其他沒認的鍵一樣不看。
# 錯：aos-eca-turn --one（call_main）照 lib 契約 stderr 與 stdout 各一行「工具名: error: 代號 原因」、退 1；attach 與 hook 是 stderr 一行「cli_session: error: 代號 原因」、退 1。
#   CLI（claude／codex）與 tmux 自己的 stderr 原樣透到 stderr、不塞進自己的錯（stdio-unify R10）；stdout 只有自己那一行（D2）。
#   給人看的狀態句（attaching、等對話空出來）是提醒行「cli_session: warning: …」（R1、D5）。工具形認 --help（英文說明印 stdout、退 0）、Ctrl-C 退 130。
# 父死子跟著死（11-10 坑-52，Linux）：非互動起的 CLI 設 PR_SET_PDEATHSIG＝SIGTERM——起它的這支（aos-eca-turn、claude／codex 工具）
#   被 kill -9／OOM，CLI 收 SIGTERM 收掉，不留孤兒拿著同一段對話跟下一輪的 --resume 撞；非 Linux 或載不到 libc 就不設。畫面（tmux）不在此列。
#
# 放哪：proto8/lib/agent/cli_session.py；claude、codex 經 agent_tool.py 的 ask_cli 共用 ask，call_main 只給 aos-eca-turn --one；
# 掛它的 agent 根目錄可以放一份 cli_session.py（或捷徑）給 attach 用（原本的例子 demo/agent-fay 11-03 晚刪了）。工具資料夾（cli.json 在裡面）由工具入口傳進來、
# agent 資料夾（attach 列 tools/）由 attach 傳進來——這支不再假設自己放在哪隻 agent 底下。
import datetime, fcntl, glob, hashlib, json, os, re, shlex, shutil, signal, socket, stat, subprocess, sys, threading, time, uuid

# hook 直接執行此檔時只補父層 lib；import 後還原，不影響呼叫者的查找順序。
_lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_added_lib = os.path.basename(_lib) == "lib" and os.path.isfile(os.path.join(_lib, "tool_io.py"))
if _added_lib:
    sys.path.insert(0, _lib)
try:
    import tool_io
finally:
    if _added_lib:
        sys.path.pop(0)
if __package__:
    from .agent_files import declared_files
else:
    from agent_files import declared_files

TMUX_SESSION = "cli"
PROG, ECHO = "cli_session", False                    # 錯誤行開頭、要不要也印到 stdout（call_main 改成工具名、True）
RESEED_BYTES, SCREEN_RESEED_BYTES = 48000, 8000      # 開新對話時紀錄的上限：cli.json 的 reseed_bytes 預設、畫面那條路的天花板（05）


def die(code, reason):
    tool_io.die(code, " ".join(str(reason).splitlines()), prog=PROG, echo=ECHO)


def warn(sentence):
    """提醒行（stdio-unify R1）：stderr 一句、不帶代號。"""
    tool_io.warn(" ".join(str(sentence).splitlines()), prog=PROG)


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
    rb = cfg.get("reseed_bytes", RESEED_BYTES)                     # 11-10 two-machines 05：開新對話時接在題目前的紀錄上限
    if not isinstance(rb, int) or isinstance(rb, bool) or rb < 0:
        die("CfgBad", "%s: reseed_bytes must be a non-negative integer" % path)
    try:
        files = declared_files(tool_dir)
    except ValueError as e:
        die("CfgBad", str(e))
    cfg["registry"] = registry(cfg, tool_dir, path, files)
    cfg["hooks_def"] = os.path.abspath(tool_dir) if files.get("hooks") else None   # 11-10 hook：宣告了 hooks＝aos-mcp 帶 --hooks
    stack_copies(cfg, tool_dir, files)
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


def stack_copies(cfg, tool_dir, files):
    """子介面 tools／llm 依 interfaces.json 宣告的相對檔名讀 stack 覆蓋；沒有宣告就不讀 stack。
    cli.json 明寫 tools 時照它、不看 stack 那份；未宣告時定義的預設登記檔仍是同層 tools.json。
    腦設定：定義宣告的 llm（沒宣告時仍可用同層 llm.json）疊 stack 宣告那份；
    有 model＝flags 的 --model 換成它（沒有就加在尾）。每次 load_cfg（每題）重讀＝下一題生效。"""
    stack = os.environ.get("AOS_STACK")
    llm = read_llm(os.path.join(tool_dir, files.get("llm", "llm.json")))
    if stack:
        rel = files.get("tools")
        copy = os.path.join(stack, rel) if rel else None
        if "tools" not in cfg and copy and cfg.get("registry"):
            cfg["own_registry"], cfg["def_registry"] = copy, cfg["registry"]   # 11-10 深夜 tools-def（「3.同一輪就生效」）：aos-mcp --own 每次重看，第一次 self_tools add 才建也看得到
        if "tools" not in cfg and copy and os.path.isfile(copy):
            cfg["registry"] = copy                   # 11-10 aos-tools-cli 步 4：這隻自己那份（"$override" 指回定義那份）在就用它
        if "llm" in files:
            llm.update(read_llm(os.path.join(stack, files["llm"])))
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


def registry(cfg, tool_dir, path, files):
    """這份定義的 aos-tools 登記檔（絕對路徑）；沒有＝None（11-03 eca-tools）。
    tools 有寫＝它（相對路徑從 cli.json 的資料夾算），不是檔＝ToolsMissing；沒寫＝interfaces.json 宣告的 tools，未宣告才取同層 tools.json。
    給了 tools_flags 卻沒有登記檔＝CfgBad（寫什麼就做什麼，不靜靜吞掉）。"""
    base = os.path.abspath(tool_dir)
    if "tools" in cfg:
        tools = cfg["tools"]
        if isinstance(tools, dict):   # 11-10 two-machines TC：寫指示詞（例 {"$env": "X", "$path": "tools.json"}）＝每次讀才解、不寫回；解完照字串的規則
            sys.path.insert(0, _lib)  # directive_value 跟 tool_io 同在 lib/（直接執行此檔時 lib 不在 sys.path）
            try:
                from directive_value import resolve_path
            finally:
                sys.path.pop(0)
            try:
                tools = resolve_path(tools, path, "tools")
            except tool_io.Error as e:
                die(e.code, str(e))
        if not isinstance(tools, str) or not tools:
            die("CfgBad", "%s: tools must be the path of a registry file (a non-empty string)" % path)
        reg = os.path.normpath(os.path.join(base, tools))
        if not os.path.isfile(reg):
            die("ToolsMissing", "%s: registry file named by tools not found: %s" % (path, reg))
        return reg
    reg = os.path.join(base, files.get("tools", "tools.json"))
    if os.path.isfile(reg):
        return reg
    if "tools_flags" in cfg:
        die("CfgBad", "%s: tools_flags given but no registry file (no tools, and no default registry alongside)" % path)
    return None


def mcp_argv(cfg, cell, ws, stack):
    """有登記檔＝接上 aos-mcp 要加給 CLI 的旗標；沒有＝[]（11-03 eca-tools）。每次起 CLI 前叫（claude 的 mcp.json 每次重寫）。
    ws＝CLI 的 cwd、stack＝給 aos-mcp 的 --stack（工具叫的小格在 <stack>/tools/<名>/）。"""
    reg = cfg.get("registry")
    if not reg:
        return []
    if cfg.get("own_registry"):                       # aos-mcp 自己挑：--own 那份在就用它，不在（reset 刪了）＝回定義那份
        reg = cfg["def_registry"]
    if not os.path.isfile(reg):                       # load_cfg 之後才被刪掉
        die("ToolsMissing", "registry file not found: %s" % reg)
    if shutil.which("aos-mcp") is None:
        die("CliMissing", "aos-mcp is not on PATH (tools are attached; add proto8/cmd/aos-mcp/bin to PATH)")
    args = ["--ws", ws, "--stack", stack] + (["--hooks", cfg["hooks_def"]] if cfg.get("hooks_def") else []) \
        + (["--own", os.path.abspath(cfg["own_registry"])] if cfg.get("own_registry") else []) \
        + cfg.get("tools_flags", []) + [reg]
    if cfg["kind"] == "codex":                           # JSON 字串與字串陣列同時是合法的 TOML（-c 的值照 TOML 解）
        return ["-c", "mcp_servers.aos.command=" + json.dumps("aos-mcp"), "-c", "mcp_servers.aos.args=" + json.dumps(args)]
    try:
        cell.write("mcp.json", json.dumps({"mcpServers": {"aos": {"command": "aos-mcp", "args": args}}},
                                          ensure_ascii=False) + "\n")
    except OSError as e:
        die("WriteFailed", "cannot write %s: %s" % (cell.file("mcp.json"), e))
    return ["--mcp-config", cell.file("mcp.json"), "--allowedTools", "mcp__aos"]


def machine_id():
    """這台機器的識別（記號檔的 machine，11-10 TS 8）：/etc/machine-id 的內容；讀不到或空的＝socket.gethostname()。"""
    try:
        with open("/etc/machine-id", encoding="utf-8") as f:
            mid = f.read().strip()
        if mid:
            return mid
    except (OSError, ValueError):
        pass
    return socket.gethostname()


TTY_HASH = 16                                            # 小格 realpath 的 sha256 取前幾個 hex（路徑短，遠低於 AF_UNIX 的 108 bytes）


def tty_base():
    """放畫面 socket 的資料夾：${XDG_RUNTIME_DIR}/aos-tty-<uid>；XDG_RUNTIME_DIR 沒設、不是資料夾、不可寫、或太長＝/tmp/aos-tty-<uid>。"""
    sub = "aos-tty-%d" % os.getuid()
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    if (os.path.isabs(xdg) and os.path.isdir(xdg) and os.access(xdg, os.W_OK | os.X_OK)
            and len(os.path.join(xdg, sub).encode()) <= 80):
        return os.path.join(xdg, sub)
    return os.path.join("/tmp", sub)


def tty_dir_ok(folder, make=False):
    """socket 的資料夾是這個使用者自己的（不是 symlink、owner 是自己）＝True；權限多給了就收回 0700。
    不在：make＝建（mode 0700）、否則 False。別人的或修不了＝False（不連別人的 tmux server）。"""
    try:
        st = os.lstat(folder)
    except FileNotFoundError:
        if not make:
            return False
        try:
            os.makedirs(folder, mode=0o700)
        except FileExistsError:
            pass
        except OSError:
            return False
        try:
            st = os.lstat(folder)
        except OSError:
            return False
    except OSError:
        return False
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        return False
    if st.st_mode & 0o077:
        try:
            os.chmod(folder, 0o700)
        except OSError:
            return False
    return True


def tty_socket(cell_path, make=False):
    """小格的畫面（tmux）socket 在哪：唯一入口（11-10 TS 10）。一律回 <tty_base()>/<小格 realpath 的短雜湊>.sock，例外只有
    「那裡沒有、但另一個候選有」：XDG_RUNTIME_DIR 有無不同的行程（daemon、人的 shell）各算出 /run/user/… 或 /tmp/…，
    兩處都看；11-10 以前開的畫面在小格的 tty.sock（過渡，只認、不建）。make＝要開新畫面：只回首選、資料夾不在就建、
    不是自己的＝CellBad。資料夾不是自己的候選一律跳過。"""
    h = hashlib.sha256(os.path.realpath(cell_path).encode()).hexdigest()[:TTY_HASH] + ".sock"
    first = os.path.join(tty_base(), h)
    if make:
        if not tty_dir_ok(os.path.dirname(first), make=True):
            die("CellBad", "%s is not a private folder of this user (cannot put the screen socket there)" % os.path.dirname(first))
        return first
    for cand in (first, os.path.join("/tmp", "aos-tty-%d" % os.getuid(), h), os.path.join(cell_path, "tty.sock")):
        try:
            is_sock = stat.S_ISSOCK(os.stat(cand).st_mode)
        except OSError:
            continue
        if is_sock and (cand.startswith(cell_path + os.sep) or tty_dir_ok(os.path.dirname(cand))):
            return cand
    return first


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

    def sock(self, make=False):
        """畫面的 tmux socket（tty_socket，11-10 TS 10；不在小格裡）。"""
        return tty_socket(self.path, make)

    def tmux(self, *args, new=False, **kw):
        """new＝開新畫面（start 的 new-session）：socket 放首選位置、資料夾不在就建。"""
        kw.setdefault("capture_output", True)
        kw.setdefault("text", True)
        return subprocess.run(["tmux", "-S", self.sock(new)] + list(args), **kw)

    def alive(self):
        if not os.path.exists(self.sock()):
            return False
        try:
            return self.tmux("has-session", "-t", TMUX_SESSION).returncode == 0
        except FileNotFoundError:            # 沒有 tmux：畫面不可能開著
            return False

    def clients(self):
        r = self.tmux("list-clients", "-t", TMUX_SESSION, "-F", "#{client_tty}")
        return [l for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []


def note_cell(cell, tool_dir, ws, stack):
    """工具、工作區、stack 都存相對小格的路徑，整樹搬遷後 open_cell 照新位置叫回。寫不成不擋正事。"""
    try:
        for name, value in (("tool.txt", tool_dir), ("ws.txt", ws), ("stack.txt", stack)):
            value = os.path.relpath(value, cell.path)
            if cell.read(name) != value:
                cell.write(name, value + "\n")
    except OSError:
        pass


def close(cell):
    """關掉畫面（tmux 和裡面的 CLI；對話是 CLI 邊講邊存的，id 留在 session.txt）。回 True＝本來開著。"""
    if not cell.alive():
        return False
    sock = cell.sock()
    cell.tmux("kill-server")
    if not sock.startswith(cell.path + os.sep):          # tmux 3.4 kill-server 後 socket 檔還留著：收掉（在小格的舊 socket 照舊不動）
        try:
            os.remove(sock)
        except OSError:
            pass
    return True


def account_dir(kind):
    """CLI 的帳號資料夾（對話存在它底下）：claude＝CLAUDE_CONFIG_DIR 或 ~/.claude；codex＝CODEX_HOME 或 ~/.codex。"""
    if kind == "claude":
        return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
    return os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")


def transcripts(kind, sid):
    """CLI 自己存的這段對話（含中間訊息、工具呼叫等副產物）放在哪：claude ~/.claude/projects/*/<id>.jsonl、
    codex ~/.codex/sessions/年/月/日/rollout-*-<id>.jsonl。小格的 transcripts/ symlink 指到這裡（10-30；10-28 是 stop 時才拷）。"""
    if not sid:
        return []
    base = account_dir(kind)
    if kind == "claude":
        return sorted(glob.glob(os.path.join(base, "projects", "*", sid + ".jsonl")))
    return sorted(glob.glob(os.path.join(base, "sessions", "**", "*%s.jsonl" % sid), recursive=True))


def mark_session(kind, cell, ws, sid):
    """寫 session.txt 與記號檔 .session_home（11-10 two-machines 05）。寫不成＝提醒一行、回 False（不擋正事：
    下一輪認不出是這台的，頂多開新對話）。"""
    try:
        cell.write("session.txt", sid + "\n")
        cell.write(".session_home", json.dumps({"session": sid, "ws": os.path.realpath(ws),
                                                "home": os.path.realpath(account_dir(kind)),
                                                "machine": machine_id()}, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        warn("cannot write %s or .session_home: %s" % (cell.file("session.txt"), e))
        return False


def drop_session(cell):
    """刪 session.txt 與 .session_home（下一次開新對話）；本來不在不算錯，刪不掉不擋（下一次 session_here 照樣認不出）。"""
    for name in ("session.txt", ".session_home"):
        try:
            os.remove(cell.file(name))
        except FileNotFoundError:
            pass
        except OSError as e:
            warn("cannot remove %s: %s" % (cell.file(name), e))


def session_here(cfg, cell, ws, sid):
    """sid 這段對話是不是在這台（這個帳號資料夾、claude 再加這個工作區）開的（11-10 two-machines 05）：看記號檔，
    session 與 home 一樣、claude 的 ws 也一樣＝True；記號檔有 machine＝再比 machine_id()（11-10 TS 8；舊記號檔沒有＝不比，
    免得已在跑的全部開新對話）。記號檔不在或讀不懂、但 transcripts() 找得到＝功能上線前就在跑的，
    當這台的、補寫記號檔（過渡補丁）。不讀 CLI 的任何檔內容、不靠它的錯誤訊息。"""
    kind = cfg["kind"]
    try:
        with open(cell.file(".session_home"), encoding="utf-8") as f:
            mark = json.load(f)
    except (OSError, ValueError):
        mark = None
    if isinstance(mark, dict) and isinstance(mark.get("session"), str) and isinstance(mark.get("home"), str):
        return (mark["session"] == sid and mark["home"] == os.path.realpath(account_dir(kind))
                and (kind != "claude" or mark.get("ws") == os.path.realpath(ws))
                and ("machine" not in mark or mark["machine"] == machine_id())
                and stored_here(cfg, ws, sid))
    if stored_here(cfg, ws, sid):
        mark_session(kind, cell, ws, sid)
        return True
    return False


def stored_here(cfg, ws, sid):
    """CLI 自己存的這段對話在這台、這個工作區找得到嗎（11-10 TA 實跑：shutdown 打斷第一輪、claude 還沒建檔就被殺，
    記號檔相符卻 resume 不到＝下一封白掉；同帳號資料夾、專案換了路徑時過渡補丁會認錯）。只看檔在不在、不讀內容：
    claude＝<帳號資料夾>/projects/<工作區真實路徑把非英數字元換成 -（照 CLI 的命名，未經真機驗證）>/<id>.jsonl；
    codex＝transcripts() 找得到。flags 帶 --no-session-persistence＝CLI 不存檔，不看（當作在）。"""
    flags = list(cfg.get("flags", [])) + list(cfg.get("print_flags", []))
    if "--no-session-persistence" in flags:
        return True
    found = transcripts(cfg["kind"], sid)
    if cfg["kind"] != "claude":
        return bool(found)
    want = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(ws))
    return any(os.path.basename(os.path.dirname(f)) == want for f in found)


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

def parent_death_term():
    """給 Popen 的 preexec_fn：子程式那側設 PR_SET_PDEATHSIG＝SIGTERM（11-10 坑-52），起它的執行緒一結束（這支被 kill -9、OOM）CLI 就收 TERM。
    設完 getppid 跟 fork 前記的不同＝父在設之前就死了，直接退。非 Linux、載不到 libc＝回 None（不設、不報錯）。
    PDEATHSIG 看的是 fork 的那條執行緒：這檔的 Popen 都在呼叫者的主執行緒起（Timer 執行緒只負責 kill）。"""
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        prctl = ctypes.CDLL(None, use_errno=True).prctl          # fork 前先找好，子程式那側只呼叫
    except (ImportError, OSError, AttributeError):
        return None
    parent = os.getpid()
    args = (ctypes.c_int(1), ctypes.c_ulong(signal.SIGTERM),       # 1＝PR_SET_PDEATHSIG
            ctypes.c_ulong(0), ctypes.c_ulong(0), ctypes.c_ulong(0))

    def preexec():
        prctl(*args)
        if os.getppid() != parent:
            os._exit(128 + signal.SIGTERM)
    return preexec


def run_cli(argv, prompt, ws, timeout_ms, handed=None):
    """起 CLI、題目從 stdin 給、等它做完；起來了就叫 handed（交出去了，11-03 aos-eca-turn 在這一刻收信）。
    CLI 的 stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, cwd=ws, preexec_fn=parent_death_term())
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
    return subprocess.CompletedProcess(argv, p.returncode, out, None)


def tail(text, n=300):
    return (text or "").strip()[-n:]


def run_claude_stream(argv, prompt, ws, timeout_ms, live_path, handed=None):
    """claude -p --output-format stream-json：每行一邊寫進 live.jsonl（人可以 tail 著看），一邊收起來；回 (結束碼, 全部行)。
    題目寫進 stdin、關掉之後叫 handed（交出去了，11-03）。claude 的 stderr 不攔、原樣透出（R10）。"""
    try:
        p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             text=True, cwd=ws, preexec_fn=parent_death_term())
    except FileNotFoundError:
        die("CliMissing", "%s is not on PATH" % argv[0])
    p.stdin.write(prompt)
    p.stdin.close()
    if handed:
        handed()
    deadline, lines = time.time() + timeout_ms / 1000, []
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
    if time.time() > deadline:
        die("CliFailed", "%s did not finish within %d s" % (argv[0], timeout_ms // 1000))
    return p.returncode, lines


def print_claude(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話：我們產 id、--session-id 給，交出去那一刻先寫 session.txt 與
    記號檔再叫呼叫者的 handed（第一輪就失敗也不留孤兒，05）。沒給 sid（None）＝照舊讀 session.txt。"""
    sid = cell.read("session.txt") if sid is None else sid
    new = "" if sid else str(uuid.uuid4())
    # 10-27：改 stream-json（--verbose 是它要的），一行一事件寫進小格的 live.jsonl，人用 aos-agent watch 看得到它正在做什麼；
    # 回答取最後一個帶 result 的那行（type: result）
    argv = ["claude", "-p", "--output-format", "stream-json", "--verbose"] + cfg.get("flags", []) + cfg.get("print_flags", [])
    argv += mcp_argv(cfg, cell, ws, stack)
    argv += ["--resume", sid] if sid else ["--session-id", new]

    def given():
        if new:
            mark_session("claude", cell, ws, new)
        if handed:
            handed()
    code, lines = run_claude_stream(argv, prompt, ws, cfg.get("timeout_ms", 600000), cell.file("live.jsonl"), given)
    out = None
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and "result" in ev:
            out = ev
    stdout = "".join(lines)
    if out is None or code != 0 or out.get("is_error"):
        if sid and not transcripts("claude", sid):          # 以為是這台的、這台卻找不到：清掉，下一封開新的（05）
            drop_session(cell)
        elif new and not transcripts("claude", new):        # 新對話第一輪就失敗、CLI 沒建出來：清掉，下一輪直接開新的（TS 9）
            drop_session(cell)
    if out is None:
        die("CliFailed", "claude exited %d with no result in its output: %s" % (code, tail(stdout)))
    if code != 0 or out.get("is_error"):   # result 行自己帶原因（例 模型不存在）就印它；stdout 尾巴會切在 JSON 中間
        why = out.get("result") if isinstance(out.get("result"), str) and out.get("result") else tail(stdout)
        die("CliFailed", "claude exited %d: %s" % (code, tail(why)))
    got = out.get("session_id")
    if new and isinstance(got, str) and got and (got != new or cell.read("session.txt") != new):
        mark_session("claude", cell, ws, got)              # result 帶了不同的 id（或交出去時沒寫成）：以它為準
    return out.get("result") or ""


def print_codex(cfg, cell, ws, stack, prompt, handed=None, sid=None):
    """sid＝要接的對話（ask 已認過是這台的）；空＝開新對話。thread id 是 codex 自己產的：不管成敗，讀到 thread.started 就寫
    session.txt 與記號檔（05）。沒給 sid（None）＝照舊讀 session.txt。"""
    sid = cell.read("session.txt") if sid is None else sid
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
    if not sid and thread:                       # 成敗之前就寫：第一輪就失敗也不留孤兒（05）
        mark_session("codex", cell, ws, thread)
    if r.returncode != 0 or not os.path.exists(last):
        if sid and not transcripts("codex", sid):           # 以為是這台的、這台卻找不到：清掉，下一封開新的（05）
            drop_session(cell)
        elif not sid and thread and not transcripts("codex", thread):   # 新 thread 第一輪就失敗、CLI 沒存檔：清掉（TS 9）
            drop_session(cell)
        die("CliFailed", "codex exited %d (its reason is on stderr)" % r.returncode)
    with open(last, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 從畫面送字（畫面開著）

# claude 在沒信任過的資料夾開畫面，會先停在「信不信任這個資料夾」的選單，預設選項是 No, exit：這時貼題目＋Enter＝選了離開、畫面關掉
# （11-10 深夜使用者選「aos 偵測後報錯」；實拍 2026-11 claude 的選單：「Quick safety check: Is this a project you created or one you trust?」
#   底下「❯ No, exit」「Yes, I trust this folder」「Enter to confirm · Esc to cancel」）。認法要耐得住小改字：畫面最後 TRUST_TAIL 行裡
#   有 trust 這個字，而且有一行像選項（前面可有 ❯／›／> 與「1.」）寫著 no, exit 或 yes … trust；認不出＝照舊貼。codex 實拍沒這種選單，不做。
TRUST_TAIL = 30
_TRUST_OPTION = re.compile(r"^\s*(?:[❯›>»]\s*)?(?:\d+[.)]\s*)?(?:no\b[^\n]{0,12}\bexit\b|yes\b[^\n]{0,40}\btrust)", re.I | re.M)


def trust_prompt(screen):
    """畫面（capture-pane 的字）是不是停在 claude 的信任資料夾選單。"""
    tail = "\n".join([l for l in (screen or "").splitlines() if l.strip()][-TRUST_TAIL:])
    return "trust" in tail.lower() and bool(_TRUST_OPTION.search(tail))


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
    if cfg.get("kind") == "claude" and trust_prompt(cell.tmux("capture-pane", "-p", "-t", TMUX_SESSION).stdout):
        ws = os.path.normpath(os.path.join(cell.path, cell.read("ws.txt") or "."))
        die("TrustMissing", "claude on the screen is waiting at its trust-this-folder prompt for %s; nothing was typed. "
            "Choose yourself: attach to the screen (aos-agent open), or run claude there once and pick trust: cd %s && claude"
            % (ws, shlex.quote(ws)))
    seen = len(cell.turns())
    r = cell.tmux("load-buffer", "-b", "aos", "-", input=prompt)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)                         # tmux 自己的話原樣透出（R10）
        die("CliFailed", "tmux load-buffer exited %d" % r.returncode)
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


def ask(cfg, cell, tool_dir, ws, stack, prompt, on_busy="yield", handed=None, reseed=None):
    """問 CLI 一句 → 回答文字：記下這格（note_cell）→ 拿格的 lock（拿不到：on_busy＝yield（預設）＝SessionBad、
    answer＝等到拿到，同 open_cell）→ 畫面開著走 live（on_busy 照傳）、沒開走非互動
    → 建 transcripts symlink。lib/agent/agent_tool.py 的 ask_cli 與 aos-eca-turn（含 --one 的 call_main）共用這一段。
    tool_dir＝cli.json 所在的資料夾（工具資料夾或 eca 定義）；ws＝CLI 的 cwd（絕對路徑）；stack＝給 aos-mcp 的 --stack
    （平級形＝那隻 eca 的 $AOS_STACK、工具形＝這格本身；11-03 eca-tools）。handed＝選填、不帶參數的函式：題目交給 CLI 的那一刻叫一次
    （非互動＝CLI 起來、題目寫進去；畫面＝貼上按 Enter），在等回答之前（11-03 aos-eca-turn 在這一刻收信；工具形不給）。錯一律走 die
    （工具形印一行退 1；aos-eca-turn 把 die 換成丟例外）。
    reseed＝選填、reseed(上限 bytes) -> 開場白（整理過的舊紀錄，結尾一個空行；沒紀錄回 ""）：這次是新對話（session.txt 沒有，
    或 session_here 認不出是這台的）就接在題目前面（11-10 two-machines 05；aos-eca-turn 給）。沒給而且是「有舊 id 但不在這台」
    ＝stderr 一行 warning、照樣開新的（工具形）。"""
    note_cell(cell, tool_dir, ws, stack)
    f, ok = cell.lock()
    if not ok:
        if on_busy == "yield":
            die("SessionBad", "this conversation is in use (another call, or attach is opening the screen)")
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        limit = cfg.get("reseed_bytes", RESEED_BYTES)
        sid = cell.read("session.txt")
        if cell.alive():                                 # 畫面開著＝這台的；session.txt 還沒有＝新對話（hook 第一輪才寫）
            if not sid and reseed:
                prompt = reseed(min(limit, SCREEN_RESEED_BYTES)) + prompt
            text = live(cfg, cell, prompt, on_busy, handed)
        else:
            if sid and not session_here(cfg, cell, ws, sid):
                if not reseed:
                    warn("the earlier conversation is not on this machine; starting a new one without its record")
                sid = ""
            if not sid and reseed:
                prompt = reseed(limit) + prompt
            if cfg["kind"] == "claude":
                text = print_claude(cfg, cell, ws, stack, prompt, handed, sid)
            else:
                text = print_codex(cfg, cell, ws, stack, prompt, handed, sid)
        link_transcript(cell, cfg["kind"])               # 工具形也留（方向題 3）
    return text


CALL_HELP = """\
usage: %(name)s < ARGUMENTS.json   (a tool: run it with aos-exec; $AOS_STACK is its cell)
Hand the prompt to the %(name)s CLI and print its answer; the conversation goes on in this
tool's cell (session.txt), and a person can attach to its screen (aos-agent attach).
How the CLI is called (flags, timeout_ms, tools) is in cli.json next to _entry.
If the earlier conversation was started on another machine, in another workspace (claude) or with another
account folder (.session_home in the cell says so), a warning is printed and a new conversation is started.
AOS_WS is required and must be a directory.
Arguments: one JSON object on stdin:
  prompt  string, required
Result on stdout. On error: one line "%(name)s: error: CODE reason" on stderr and stdout, exit 1
(the CLI's own stderr is passed through to stderr).
"""


def call_main(tool_dir, on_busy="yield"):
    """aos-eca-turn --one 入口：stdin {"prompt": "..."} → stdout 回答。tool_dir＝定義資料夾（cli.json 在裡面；名字＝資料夾名）。
    on_busy 照 --on-busy 傳給 ask；lib 的 claude／codex 改由 agent_tool.py 的 ask_cli 呼叫 ask。"""
    global PROG, ECHO
    PROG, ECHO = os.path.basename(tool_dir), True
    if "--help" in sys.argv[1:]:                         # --help：英文說明印 stdout、退 0（stdio-unify R3）
        sys.stdout.write(CALL_HELP % {"name": PROG})
        sys.exit(0)
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))   # Ctrl-C：不吐 traceback、退 130（R12）
    cfg = load_cfg(tool_dir)
    stack, ws = os.environ.get("AOS_STACK"), os.environ.get("AOS_WS")
    if not stack:
        die("StackMissing", "AOS_STACK is not set")
    if not ws or not os.path.isdir(ws):
        die("WsMissing", "AOS_WS is not set or not a directory")
    ws = os.path.realpath(ws)
    try:
        args = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        die("ArgumentsBad", "stdin is not JSON")
    if not isinstance(args, dict) or not isinstance(args.get("prompt"), str) or not args["prompt"].strip():
        die("ArgumentsBad", "missing prompt (a non-empty string)")
    cell = Cell(stack)                                   # 工具形：對話在這格本身，aos-mcp 的 stack 也是它（它叫的工具再疊 tools/<名>/）
    text = ask(cfg, cell, os.path.abspath(tool_dir), ws, cell.path, args["prompt"], on_busy)
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
            ws = cell.read("ws.txt")                       # 記號檔要工作區：從小格的 ws.txt 解相對路徑（不知道就只寫 session.txt，
            if ws:                                         # 下一次 session_here 走過渡補丁補寫）
                mark_session(kind, cell, os.path.normpath(os.path.join(cell.path, ws)), sid)
            else:
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
    """畫面沒開就開一個（在 tmux 裡、背景）；有對話而且是這台的就接著那段，沒有或不是這台的就開新的。有登記檔＝跟非互動同一段接上 aos-mcp（11-03 eca-tools）。"""
    if cell.alive():
        return False
    sid = cell.read("session.txt")
    if sid and not session_here(cfg, cell, ws, sid):     # 不是這台的（換台、搬位置、換帳號資料夾）：清掉、開新的（05）
        drop_session(cell)
        sid = ""
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
                      "-x", "160", "-y", "45", "-c", ws, "--", *argv, new=True)
    except FileNotFoundError:
        die("TmuxMissing", "tmux is not on PATH")
    if r.returncode != 0:
        sys.stderr.write(r.stderr)                         # tmux 自己的話原樣透出（R10）
        die("CliFailed", "tmux new-session exited %d" % r.returncode)
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
        print("%s screen %s: %s" % (names[0], "opened" if opened else "already open", cell.sock()))
        return
    warn("attaching to %s (Ctrl-\\ detaches, the screen stays; /exit inside to end)" % names[0])
    os.execvp("tmux", ["tmux", "-S", cell.sock(), "attach", "-t", TMUX_SESSION])


def open_cell(cell):
    """畫面沒開就開（有 session.txt 就 --resume 接回那段＝叫回）；tool.txt、ws.txt、stack.txt 都從小格解相對路徑。回 True＝這次才開的。
    stack.txt 只在接了工具時要（沒有＝CellBad；11-03 eca-tools）。"""
    tool_dir, ws, stack = cell.read("tool.txt"), cell.read("ws.txt"), cell.read("stack.txt")
    if not tool_dir or not ws:
        die("CellBad", "%s has no tool.txt/ws.txt (not a cell cli_session has used)" % cell.path)
    tool_dir = os.path.normpath(os.path.join(cell.path, tool_dir))
    ws = os.path.normpath(os.path.join(cell.path, ws))
    stack = os.path.normpath(os.path.join(cell.path, stack)) if stack else ""
    cfg = load_cfg(tool_dir)
    if cfg.get("registry") and not stack:
        die("CellBad", "%s has no stack.txt (tools are attached; need the stack for aos-mcp)" % cell.path)
    f, ok = cell.lock()
    if not ok:
        warn("the agent is using this conversation; waiting for its turn to finish...")
        fcntl.flock(f, fcntl.LOCK_EX)
    with f:
        return start(cfg, cell, ws, stack)


if __name__ == "__main__":
    if "--help" in sys.argv[1:2]:
        print("usage: cli_session.py hook claude|codex CELL [PAYLOAD]\n"
              "The hook the CLI's interactive screen calls after each turn (appends to CELL/turns.jsonl; never fails).\n"
              "Tool entries (lib/agent/claude, codex), aos-eca-turn and aos-eca-screen import this file.")
    elif len(sys.argv) >= 4 and sys.argv[1] == "hook":
        hook_main(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        die("ArgumentsBad", "expected hook claude|codex CELL [PAYLOAD] (usage: cli_session.py hook claude|codex CELL [PAYLOAD]; see --help)")
