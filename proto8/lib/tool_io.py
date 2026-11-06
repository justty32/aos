"""tool_io - lib 工具共用的開頭：--help、Ctrl-C、錯誤行／提醒行、讀 stdin 參數、查工作區。

使用者 11-05 裁「收成共用模組」（thinking 2026-11-05 stdio-unify § 剩下的；原則「統一成單一介面，這樣只需要改介面」）：
錯誤行與提醒行的格式只寫在這裡，各工具不自己拼字串。不是工具（沒有 _entry），是 lib 最底下的共用模組；純標準庫。

工具怎麼找到它（lib/docs/01 規則 9）：先找工具自己的資料夾（複製出 lib 的工具，把這支一起複製進去），再找 lib/（工具資料夾往上兩層）：
    HERE = os.path.dirname(os.path.realpath(__file__))
    sys.path[:0] = [HERE, os.path.dirname(os.path.dirname(HERE))]
    import tool_io
沙箱裡要看得到這支：綁工具資料夾時把它也綁唯讀（例 cmd/aos-sandbox/examples/bash-boxed/sandbox.json 的 ro）。

形狀（lib 契約，lib/docs/01 規則 3、5、5a）：
  錯誤行  「<名>: error: <代號> <原因>」：stderr 一行；給腦用的工具（預設）stdout 也印同一行（stdout 是給腦看的結果）；退 1。
  提醒行  「<名>: warning: <句子>」：只在 stderr、不帶代號。
  --help  argv 有 --help＝英文說明印 stdout、退 0。
  Ctrl-C  不吐 traceback、退 130（有子行程的工具自己再接 SIGINT，先收那一群）。
  讀的人先關了 stdout（EPIPE，例 `| head -c0`）＝照 Unix 預設被 SIGPIPE 打掉、退 141（128＋13），不吐 traceback（11-05 晚邊緣測試）。"""
import json, os, signal, sys

NAME = "tool"
ECHO = True                                     # 錯誤行要不要也印到 stdout


def start(name, help_text, echo=True):
    """工具開頭叫一次：記下名字；argv 有 --help 就印說明退 0；Ctrl-C 退 130。echo=False：錯誤行只到 stderr（不是給腦用的，例 judge）。"""
    global NAME, ECHO
    NAME, ECHO = name, echo
    if "--help" in sys.argv[1:]:
        sys.stdout.write(help_text)
        sys.exit(0)
    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(130))
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # stdout 被關＝安靜退 141；Python 預設是 BrokenPipeError traceback、退 120


def error_line(code, reason):
    return "%s: error: %s %s" % (NAME, code, str(reason).replace("\n", " "))


def die(code, reason, before=""):
    """印錯誤行、退 1。before＝錯誤行之前先印到 stdout 的東西（例 bash 截到一半的輸出）。"""
    line = error_line(code, reason)
    print(line, file=sys.stderr, flush=True)
    if ECHO:
        sys.stdout.write(before + line + "\n")
        sys.stdout.flush()
    sys.exit(1)


def warn(sentence):
    print("%s: warning: %s" % (NAME, str(sentence).replace("\n", " ")), file=sys.stderr, flush=True)


def workspace():
    """$AOS_WS 的真實路徑；沒設或不是資料夾＝WsMissing。"""
    ws = os.environ.get("AOS_WS")
    if not ws or not os.path.isdir(ws):
        die("WsMissing", "AOS_WS is not set or not a directory")
    return os.path.realpath(ws)


def arguments(*required):
    """stdin 的 JSON 物件（空＝{}）；required 列的 key 一定要是非空字串。"""
    try:
        a = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        die("ArgumentsBad", "stdin is not JSON")
    if not isinstance(a, dict):
        die("ArgumentsBad", "arguments must be an object")
    for k in required:
        if not isinstance(a.get(k), str) or not a[k]:
            die("ArgumentsBad", "missing %s (a string)" % k)
    return a
