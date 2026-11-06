"""aos_flags：命令列旗標解析（含共用短名）、互動確認與三扇門的共用小函式（10-21 plan L1；11-05 stdio-unify 加錯誤行、提醒行、--help、Ctrl-C；11-06 human-cli 加短名、確認；11-06 json-argv J5 切 token 改包 lib/tool_io.py 的 tokenize_flags、stdout 被關退 141）。純標準庫＋隔壁 lib/tool_io.py。
aos 自己的 Python 程式（cmd/ 的 aos-tick、aos-tools、aos-daemon-ctl、aos-agent、aos-mcp、aos-grow、aos-sandbox…）都用它，
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
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。
可以重複給、每次都收的旗標（11-04，aos-grow 的 `--take`）另給一張表 multi：opts[值]＝照給的順序的字串串列（沒給＝沒這個 key）。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
`--help`（11-05 stdio-unify R3，使用者「全都有」「--help要輸出英文」）：旗標的位置（子命令後再 parse 一次也算）看到 `--help`＝把 HELP
（或 parse 的 help 參數）印到 stdout、退 0；兩個都沒設＝跟別的不認得的旗標一樣 FlagUnknown。`--help=x`＝ArgumentsBad。
錯誤行與提醒行（R1，使用者「可以，固定格式："error:", "warning:"後面接你那個」）：stderr 只有兩種行——
`程式: error: 代號 原因`（有它就不准退 0）、`程式: warning: 句子`（不帶代號，可以退 0）。usage 放原因後面：`原因 (usage: …)`（R5）。
原因裡的換行換成空白（一行就是一行）。
短名（11-06 human-cli H4，使用者裁「開幾個常用短名」）：全 aos 共用一張表 SHORT（九個），同一短名在所有指令同義、沒列在表上的不准開；
每支用 parse 的 short 參數從表裡挑自己有的長旗標對應的短名（不在表上、或對應的長旗標不在這次的 flags／switches／multi＝ValueError，
是程式寫錯）。`-h` 內建：認 `--help` 的地方 `-h` 也認，不用列。不黏值（`-tann`）、不併（`-jf`）、不帶 `=`（`-t=x`）：單槓 token
整個當旗標名，不是開了的短名＝FlagUnknown `unknown flag 整個token`；錯誤訊息用使用者打的名字（`-t needs a value`）。
C++ 的 aos::parse_cli 之後加同一張表（kShort）。
切 token（--x V／--x=V／--／開關帶值／缺值）用 lib/tool_io.py 的 tokenize_flags（json-argv J5，去重；找法＝本檔真位置的 ../lib），
這裡只管旗標表、短名、--help；所以 aos_flags.py 單獨複製出 repo 不能用，要連 lib/tool_io.py 一起、維持 py/ 與 lib/ 同層。
確認（11-06 human-cli H11，使用者裁「終端問、非終端不問」＋「幫我加上--yes跳過」）：confirm(程式, 問句, yes)——yes 或 stdin 不是終端＝True、不問；
終端＝stderr 問 `程式: 問句 [y/N] `、只有 y／yes 算答應，其他與 EOF 都是 No。答 No 呼叫者印 `warning: nothing done`、退 0；Ctrl-C 交給 run 退 130。

錯誤代號（代號照 10-23 命名統合（thinking/2026-10/23/naming）；使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——
parse：不認得的旗標 FlagUnknown、其他（缺值、開關帶值）ArgumentsBad。"""
import os, select, sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")   # <py>/../lib：tokenize_flags 在 lib/tool_io.py
sys.path.insert(0, _LIB)
try:
    import tool_io  # noqa: E402  旗標切法只這一份（json-argv J5）
finally:
    sys.path.remove(_LIB)   # 不把 lib/ 留在呼叫者的 sys.path（lib/aos、lib/agent 會變成同名 namespace package）

HELP = None

# 全 aos 共用短名表（human-cli H4，使用者 11-06「開幾個常用短名」）：同名同義，沒列的不准開。
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


def parse(argv, flags, switches=None, multi=None, help=None, short=None):
    switches, multi = switches or {}, multi or {}
    text = help if help is not None else HELP
    builtin_help = text is not None and "--help" not in flags and "--help" not in switches
    alias = {}  # 這次開的短名 → 長旗標（呼叫者寫錯＝ValueError，不是使用者的錯）
    for s in short or ():
        if s not in SHORT:
            raise ValueError("short flag %r is not in aos_flags.SHORT" % (s,))
        if s != "-h" and SHORT[s] not in flags and SHORT[s] not in switches and SHORT[s] not in multi:
            raise ValueError("short flag %s needs %s in flags, switches or multi" % (s, SHORT[s]))
        alias[s] = SHORT[s]
    if builtin_help:
        alias["-h"] = "--help"
    seen_help = []

    def key_of(flag):  # 單槓 token 整個是名（tool_io 不切 =），查短名；雙槓照原樣
        return flag if flag.startswith("--") else alias.get(flag, flag)

    def kind(flag):  # tokenize_flags 照 argv 順序叫；前一個 --help 沒帶值（沒被當錯）就在這裡印說明
        if seen_help:
            _print_help(text)
        key = key_of(flag)
        if key == "--help" and builtin_help:
            seen_help.append(flag)
            return "switch"  # --help=x 由 tokenize_flags 報 ArgumentsBad「--help takes no value」
        if key in switches:
            return "switch"
        return "value" if key in flags or key in multi else None

    try:
        pairs, rest = tool_io.tokenize_flags(argv, kind)
    except tool_io.Error as e:
        raise Error(str(e), e.code) from None
    if seen_help:
        _print_help(text)
    opts = {}
    for flag, val in pairs:
        key = key_of(flag)
        if key in switches:
            opts[switches[key]] = True
        elif key in multi:
            opts.setdefault(multi[key], []).append(val)
        else:
            opts[flags[key]] = val
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
