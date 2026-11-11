"""aos_flags：命令列旗標解析（含各支自定短名）、互動確認、公開狀態窗讀取與三扇門的共用小函式（10-21 plan L1；11-05 stdio-unify 加錯誤行、提醒行、--help、Ctrl-C；11-06 human-cli 加短名、確認；11-06 json-argv J5 切 token 改包 lib/tool_io.py 的 tokenize_flags、stdout 被關退 141）。純標準庫＋lib/tool_io.py。
aos 自己的 Python 程式（cmd/ 的 aos-clock、aos-tools、aos-daemon-ctl、aos-agent、aos-mcp、aos-grow、aos-sandbox…）都用它，
形狀照 CONVENTION P-44「aos 自己程式的命令列形狀」（11-04；C++ 那邊是 aos-util 的 aos::parse_cli）。
Python 版 aos-exec、aos-loop、aos-daemon、aos-fsm 10-23 刪了，只有它們用的 load_cfg（設定檔讀取）、target（目標的寫法）跟著拿掉，在 git 歷史。

    import aos_flags
    aos_flags.HELP = HELP                                # 英文說明全文（11-05 R3）；設了 parse 才認 --help
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)；e.code＝錯誤代號
    aos_flags.die(PROG, "ArgumentsBad", "missing FILE (usage: ...)")   # stderr 一行 `PROG: error: 代號 原因`、退 1
    aos_flags.warn(PROG, "the letter is still in the mailbox")           # stderr 一行 `PROG: warning: 句子`，不退出
    aos_flags.run(main)                                  # 跑 main；Ctrl-C＝不吐 traceback、退 130；stdout 被對面關＝安靜退 141
    opts, rest = aos_flags.parse(argv, {"--target": "target"}, short=("-t",))   # -t ann 等同 --target ann
    if not aos_flags.confirm(PROG, "remove fsm_ann?", yes=opts.get("yes", False)):  # switches 有 --yes 才有；終端才問
        aos_flags.warn(PROG, "nothing done"); return                        # 答 No＝提醒行、退 0

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。帶值的旗標寫 `--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。
11-10 cli-sweep Q1（使用者「1.收。2.收。3.好。」）：每一層（程式、子命令、動作）是一個節點，屬於某一層的旗標可以寫在
那一層名字之後的任何位置。opt-in：程式入口 parse(..., sub="root")、中間派發的那層 sub=True（解到下一層的名字為止、
把自己的表推進去）；之後的 parse（動作那層）位置參數後的旗標也收、外層的旗標也認（值寫回外層那份 opts，近的同名先算）；
keep=N＝第 N 個位置參數起原樣交出（訊息、內容這類原樣交給別人的）；位置參數後的 --＝連它一起原樣交出；
hide(旗標…)＝下層不再認外層的這幾個。沒有 sub="root" 的程式照舊規則。
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。
可以重複給、每次都收的旗標（11-04，aos-grow 的 `--take`）另給一張表 multi：opts[值]＝照給的順序的字串串列（沒給＝沒這個 key）。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
`--help`（11-05 stdio-unify R3，使用者「全都有」「--help要輸出英文」）：旗標的位置（子命令後再 parse 一次也算）看到 `--help`＝把 HELP
（或 parse 的 help 參數）印到 stdout、退 0；前個帶值旗標的值、第一個位置參數後與 `--` 後都不觸發；兩個都沒設＝跟別的不認得的旗標一樣 FlagUnknown。`--help=x`＝ArgumentsBad。
錯誤行與提醒行（R1，使用者「可以，固定格式："error:", "warning:"後面接你那個」）：stderr 只有兩種行——
`程式: error: 代號 原因`（有它就不准退 0）、`程式: warning: 句子`（不帶代號，可以退 0）。usage 放原因後面：`原因 (usage: …)`（R5）。
原因裡的換行換成空白（一行就是一行）。
短名（11-07 使用者裁定 sol 審查 #22）：每支指令各自定，可不同義；SHORT 是常用預設。
short 傳短名字串序列時從 SHORT 挑，傳 {短名: 長旗標} 時用自己的表；長旗標須在這次的 flags／switches／multi。
`-h` 隨內建 help 開啟；短名不黏值、不併、不帶 `=`，整個 token 是旗標名。
切 token（--x V／--x=V／--／開關帶值／缺值）用 lib/tool_io.py 的 tokenize_flags（json-argv J5，去重），
這裡只管旗標表、短名、--help；依序找自身資料夾、真位置祖先的 lib/，再用 Python 標準搜尋路徑（含 .pth）。
確認（11-06 human-cli H11，使用者裁「終端問、非終端不問」＋「幫我加上--yes跳過」）：confirm(程式, 問句, yes)——yes 或 stdin 不是終端＝True、不問；
終端＝stderr 問 `程式: 問句 [y/N] `、只有 y／yes 算答應，其他與 EOF 都是 No。答 No 呼叫者印 `warning: nothing done`、退 0；Ctrl-C 交給 run 退 130。

錯誤代號（代號照 10-23 命名統合（thinking/2026-10/23/naming）；使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——
parse：不認得的旗標 FlagUnknown、其他（缺值、開關帶值）ArgumentsBad。"""
import errno, json, os, select, sys

# 共用模組只在 import 時加入需要的根，避免 lib/ 的同名 namespace 留在呼叫者路徑。
from pathlib import Path

_import_paths = [str(Path(__file__).resolve().parent)]
for _parent in Path(__file__).resolve().parents:
    _lib = _parent / "lib"
    if (_lib / "tool_io.py").is_file():
        _import_paths.append(str(_lib))
        break
sys.path[:0] = _import_paths
try:
    import tool_io  # noqa: E402  旗標切法只這一份（json-argv J5）
finally:
    for _path in _import_paths:
        sys.path.remove(_path)

# 缺鐘檔提醒與 lib 共用同一份去重狀態，呼叫者不用知道底層模組。
warn_missing_clock = tool_io.warn_missing_clock

HELP = None

# 常用短名預設；呼叫端可傳自己的對照表（11-07 使用者裁定 sol 審查 #22）。
SHORT = {"-h": "--help", "-j": "--json", "-t": "--target", "-d": "--daemon", "-n": "--name",
         "-w": "--ws", "-s": "--stack", "-f": "--follow", "-y": "--yes"}


class Error(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.code = code


def _one(s):
    return " ".join(str(s).splitlines())


def error_line(prog, code, reason):
    """`程式: error: 代號 原因`（不帶換行）。"""
    return "%s: error: %s %s" % (prog, code, _one(reason))


def die(prog, code, reason, also_stdout=False):
    """印錯誤行到 stderr（also_stdout＝stdout 也印同一行：給腦用的工具形，lib 契約）、退 1。"""
    line = error_line(prog, code, reason)
    if also_stdout:
        print(line, flush=True)
    print(line, file=sys.stderr, flush=True)
    sys.exit(1)


def warn(prog, sentence):
    """提醒行 `程式: warning: 句子` 到 stderr（不退出）。"""
    print("%s: warning: %s" % (prog, _one(sentence)), file=sys.stderr, flush=True)


# aos 自己塞進對話、會被腦當內容讀到的話（不是 stderr 的錯誤行／提醒行）一律 `[aos] 種類: 內容`
# （使用者 11-10 深夜：「history summary那塊，或許可以稍微美化一下？…[aos] warning: ....，或是[aos] summary: ...」「2.好，統一。」）。
# 種類一個小寫詞，現有：summary（history 摘要）、session（eca 換新對話的開場）、clock（時鐘信）、hook（hook 攔下工具）、
#   tool（工具逾時／退非 0／stderr 尾巴的附註）、warning（出了狀況但照樣問腦，例：知識庫讀不到）、knowledge（system 裡的知識庫根）、
#   new_mail（信箱有新信，lib/agent/mail_notify 寄進 queue；lib 不 import py，那支自己拼同一個格式，11-11 使用者原例「[aos] new_mail: …」）、
#   goal（agent 自己停下來時丟的目標提醒，agent-fsm idle.py 與 aos-eca-turn 經 lib/agent/goal_state.py 拼，11-11 thinking goal/02）、
#   fork（工具 fork 給分身的開場與補上的工具結果，lib/agent/fork 與 lib/agent/fork_copy.py 自己拼，11-11 thinking fork-and-do-task/01）。新種類加在這裡。
NOTE_KINDS = ("summary", "session", "clock", "hook", "tool", "warning", "knowledge", "new_mail", "goal", "fork")


def aos_note(kind, text):
    """`[aos] 種類: 內容`（不帶結尾換行；內容可多行）。種類不在 NOTE_KINDS＝ValueError（新種類先登記）。"""
    if kind not in NOTE_KINDS:
        raise ValueError("unknown aos note kind %r (known: %s)" % (kind, ", ".join(NOTE_KINDS)))
    return "[aos] %s: %s" % (kind, text)


# 去重含 pid，fork 後的子行程仍會各自提醒一次。
_window_warnings = set()


def read_window(prog, path):
    """公開狀態窗：缺檔安靜；不可讀或非物件提醒一次，皆當作缺檔。"""
    try:
        with open(path, encoding="utf-8") as fh:
            value = json.load(fh)
    except OSError as exc:
        if exc.errno == errno.ENOENT:
            try:
                os.lstat(path)
            except OSError as entry_exc:
                if entry_exc.errno == errno.ENOENT:
                    return None
                exc = entry_exc
        reason = "cannot read file: %s" % exc.strerror
    except (ValueError, UnicodeError):
        reason = "invalid JSON"
    else:
        if isinstance(value, dict):
            return value
        reason = "root is not an object"
    key = (os.getpid(), os.path.abspath(path))
    if key not in _window_warnings:
        _window_warnings.add(key)
        warn(prog, "%s is unreadable (%s); treating it as missing" % (path, reason))
    return None


def run(main):
    """跑 main()；Ctrl-C（KeyboardInterrupt）＝不吐 traceback、退 130（R12）。
    讀的人先關了 stdout（`| head -1`）＝不吐 traceback、退 141（128＋SIGPIPE，human-cli 05 第 7 條）：接 BrokenPipeError
    （含 main 結束或 sys.exit 後最後那次 flush），stdout 換成 /dev/null 再退。不把 SIGPIPE 設回預設——run 包的程式常寫
    子行程的 stdin，預設會讓它們在子行程先退時被無聲打死；寫子行程 stdin 撞到的 BrokenPipeError（stdout 還好好的）照舊往外丟。"""
    try:
        try:
            main()
        finally:
            if sys.stdout is not None and not sys.stdout.closed:
                sys.stdout.flush()
    except KeyboardInterrupt:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        sys.exit(130)
    except BrokenPipeError:
        if not _stdout_gone():
            raise
        null = os.open(os.devnull, os.O_WRONLY)
        os.dup2(null, sys.stdout.fileno())
        sys.exit(141)


def _stdout_gone():
    """stdout 那頭沒人讀了嗎（Linux：pipe 的寫端沒有讀的人＝poll 回 POLLERR）。"""
    try:
        p = select.poll()
        p.register(sys.stdout.fileno(), 0)
        return any(ev & (select.POLLERR | select.POLLHUP) for _, ev in p.poll(0))
    except (AttributeError, OSError, ValueError):
        return False


def _print_help(text):
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()
    sys.exit(0)


# 11-10 cli-sweep Q1（使用者「1.收。2.收。3.好。」）：每一層（程式、子命令、動作）是一個節點，
# 屬於某一層的旗標可以寫在那一層名字之後的任何位置。派發的那層 parse(..., sub=True) 把自己的旗標表推進來，
# 下層（直到動作那層）也認得它們、值寫回那層回傳的 opts。sub="root" 先清空（程式的入口）。
_scopes = []          # [(flags, switches, multi, alias, opts)]，外到內


class _HelpNow:
    """包 kind：前一個 --help 沒帶值（沒被當錯）＝下一次被叫時就印說明（舊行為：後面寫錯也先印說明）。"""
    def __init__(self, kind, seen, text):
        self.kind, self.seen, self.text = kind, seen, text

    def __call__(self, flag):
        if self.seen:
            _print_help(self.text)
        return self.kind(flag)


def _alias_of(flags, switches, multi, short, builtin_help):
    try:
        selected = short if isinstance(short, dict) else {s: SHORT[s] for s in short or ()}
    except KeyError as e:
        raise ValueError("short flag %r has no default; pass a mapping" % e.args[0]) from None
    alias = {}  # 這次開的短名 → 長旗標（呼叫者寫錯＝ValueError，不是使用者的錯）
    for s, long_flag in selected.items():
        if not s.startswith("-") or s.startswith("--") or len(s) != 2:
            raise ValueError("invalid short flag %r" % s)
        if long_flag != "--help" and long_flag not in flags and long_flag not in switches and long_flag not in multi:
            raise ValueError("short flag %s needs %s in flags, switches or multi" % (s, long_flag))
        alias[s] = long_flag
    if builtin_help:
        alias["-h"] = "--help"
    return alias


def hide(*names):
    """外層的這些長旗標，下層不再認（例：aos-agent ctl rm 不收 --target，後面寫了＝FlagUnknown，不默默寫回頂層）。"""
    for i, (flags, switches, multi, alias, opts) in enumerate(_scopes):
        flags = {k: v for k, v in flags.items() if k not in names}
        switches = {k: v for k, v in switches.items() if k not in names}
        multi = {k: v for k, v in multi.items() if k not in names}
        alias = {k: v for k, v in alias.items() if v not in names}
        _scopes[i] = (flags, switches, multi, alias, opts)


def parse(argv, flags, switches=None, multi=None, help=None, short=None, *, sub=None, keep=None):
    """sub＝None：外層沒推過表＝舊規則（第一個位置參數起不再解）；推過＝動作那層：位置參數後的旗標也收、外層旗標也認。
    sub＝True／"root"：派發的一層，解到第一個位置參數（下一層的名字）為止，再把自己的表推進去。
    keep＝N（動作那層）：第 N 個位置參數起原樣交出、不再解（後面要原樣交給別人的那類）。
    -- 結束解析：在任何位置參數前＝丟掉它；之後＝連它一起原樣留在 rest（呼叫者看得到 XXX -- ARGS）。"""
    switches, multi = switches or {}, multi or {}
    if sub == "root":
        _scopes.clear()
    text = help if help is not None else HELP
    builtin_help = text is not None and "--help" not in flags and "--help" not in switches
    alias = _alias_of(flags, switches, multi, short, builtin_help)
    anywhere = sub is None and bool(_scopes)
    opts = {}
    own = (flags, switches, multi, alias, opts)
    scopes = [own] + list(reversed(_scopes))          # 近的先認（同名＝這層的）

    def find(flag):
        for sc in scopes:
            f, sw, mu, al, _ = sc
            key = flag if flag.startswith("--") else al.get(flag, flag)
            if key == "--help" and sc is own and builtin_help:
                return sc, key, "help"
            if key in sw:
                return sc, key, "switch"
            if key in f or key in mu:
                return sc, key, "value"
        return None, flag, None

    def kind(flag):  # tokenize_flags 照 argv 順序叫；--help 一看到就印（--help=x 先由 tokenize_flags 報）
        sc, key, k = find(flag)
        if k == "help":
            seen_help.append(flag)
            return "switch"
        return k

    seen_help = []
    try:
        pairs, rest = tool_io.tokenize_flags(argv, _HelpNow(kind, seen_help, text), anywhere, keep)
    except tool_io.Error as e:
        raise Error(str(e), e.code) from None
    if seen_help:
        _print_help(text)
    for flag, val in pairs:
        sc, key, k = find(flag)
        f, sw, mu, _, out = sc
        if key in sw:
            out[sw[key]] = True
        elif key in mu:
            out.setdefault(mu[key], []).append(val)
        else:
            out[f[key]] = val
    if sub:
        _scopes.append(own)
    return opts, rest


def confirm(prog, question, yes=False):
    """不可逆動作前問一句（H11）：yes 為真或 stdin 不是終端＝True、不問；否則 stderr 印
    `程式: 問句 [y/N] `、讀一行，只有 y／yes（不分大小寫）算 True，其他字、空行、EOF、解碼錯都是 False。
    回 False 時呼叫者印 warn(prog, "nothing done")、退 0（答 No 是正常路）。Ctrl-C 不攔，交給 run 退 130。"""
    if yes or sys.stdin is None or not sys.stdin.isatty():
        return True
    sys.stderr.write("%s: %s [y/N] " % (prog, _one(question)))
    sys.stderr.flush()
    try:
        line = sys.stdin.readline()
    except UnicodeDecodeError:
        return False
    if not line:
        sys.stderr.write("\n")
        sys.stderr.flush()
        return False
    return line.strip().lower() in ("y", "yes")
