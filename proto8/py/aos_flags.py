"""aos_flags：命令列旗標解析與三扇門的共用小函式（10-21 plan L1；11-05 stdio-unify 加錯誤行、提醒行、--help、Ctrl-C）。純標準庫。
aos 自己的 Python 程式（cmd/ 的 aos-tick、aos-tools、aos-daemon-ctl、aos-agent、aos-mcp、aos-grow、aos-sandbox…）都用它，
形狀照 CONVENTION P-44「aos 自己程式的命令列形狀」（11-04；C++ 那邊是 aos-util 的 aos::parse_cli）。
Python 版 aos-exec、aos-loop、aos-daemon、aos-fsm 10-23 刪了，只有它們用的 load_cfg（設定檔讀取）、target（目標的寫法）跟著拿掉，在 git 歷史。

    import aos_flags
    aos_flags.HELP = HELP                                # 英文說明全文（11-05 R3）；設了 parse 才認 --help
    opts, rest = aos_flags.parse(argv, {"--ws": "ws"})   # 錯丟 aos_flags.Error(原因)；e.code＝錯誤代號
    aos_flags.die(PROG, "ArgumentsBad", "missing FILE (usage: ...)")   # stderr 一行 `PROG: error: 代號 原因`、退 1
    aos_flags.warn(PROG, "daemon is not running")                       # stderr 一行 `PROG: warning: 句子`，不退出
    aos_flags.run(main)                                  # 跑 main；Ctrl-C＝不吐 traceback、退 130

規則（10-21 ideas § 3）：`[旗標...] XXX [args...]`——第一個不是旗標的參數（不以 - 開頭，或就是 -）起全部是 rest
（rest[0]＝XXX，之後原樣，不再解析旗標）；`--` 結束旗標（XXX 可以 - 開頭）。帶值的旗標寫 `--x V` 或 `--x=V`，
重複給＝最後一個算。opts＝{旗標表的值: 字串}。
不帶值的旗標（開關，10-22 `--dotenv-override`）另給一張表 switches：給了＝opts[值] 是 True，重複給＝一樣，寫 `--x=V`＝Error。
可以重複給、每次都收的旗標（11-04，aos-grow 的 `--take`）另給一張表 multi：opts[值]＝照給的順序的字串串列（沒給＝沒這個 key）。不認得的旗標、旗標缺值＝Error；有沒有 XXX 由呼叫者自己判斷（rest 可能是空的）。
`--help`（11-05 stdio-unify R3，使用者「全都有」「--help要輸出英文」）：旗標的位置（子命令後再 parse 一次也算）看到 `--help`＝把 HELP
（或 parse 的 help 參數）印到 stdout、退 0；兩個都沒設＝跟別的不認得的旗標一樣 FlagUnknown。`--help=x`＝ArgumentsBad。
錯誤行與提醒行（R1，使用者「可以，固定格式："error:", "warning:"後面接你那個」）：stderr 只有兩種行——
`程式: error: 代號 原因`（有它就不准退 0）、`程式: warning: 句子`（不帶代號，可以退 0）。usage 放原因後面：`原因 (usage: …)`（R5）。
原因裡的換行換成空白（一行就是一行）。split_line 是反過來拆這一行（只給明文例外用：aos-agent 讀 aos-daemon-ctl 的錯，C-52）。

錯誤代號（代號照 10-23 命名統合（thinking/2026-10/23/naming）；使用者 10-22「錯誤訊息多代號也遵循」）：Error 帶 code——
parse：不認得的旗標 FlagUnknown、其他（缺值、開關帶值）ArgumentsBad。"""
import sys

HELP = None


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


def split_line(line):
    """`程式: error: 代號 原因` → (程式, 代號, 原因)；不是這個形狀＝None。"""
    prog, sep, rest = line.partition(": error: ")
    if not sep or not prog or " " in prog:
        return None
    code, _, why = rest.partition(" ")
    return (prog, code, why) if code else None


def run(main):
    """跑 main()；Ctrl-C（KeyboardInterrupt）＝不吐 traceback、退 130（R12）。"""
    try:
        main()
    except KeyboardInterrupt:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        sys.exit(130)


def _print_help(text):
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    sys.stdout.flush()
    sys.exit(0)


def parse(argv, flags, switches=None, multi=None, help=None):
    opts, i, switches, multi = {}, 0, switches or {}, multi or {}
    text = help if help is not None else HELP
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-") or a == "-":
            break
        name, eq, val = a.partition("=")
        if name == "--help" and text is not None and "--help" not in flags and "--help" not in switches:
            if eq:
                raise Error("--help takes no value", "ArgumentsBad")
            _print_help(text)
        if name in switches:
            if eq:
                raise Error("%s takes no value" % name, "ArgumentsBad")
            opts[switches[name]] = True
            i += 1
            continue
        if name not in flags and name not in multi:
            raise Error("unknown flag %s" % name, "FlagUnknown")
        if not eq:
            i += 1
            if i == len(argv):
                raise Error("%s needs a value" % name, "ArgumentsBad")
            val = argv[i]
        if name in multi:
            opts.setdefault(multi[name], []).append(val)
        else:
            opts[flags[name]] = val
        i += 1
    return opts, argv[i:]
