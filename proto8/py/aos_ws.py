"""aos_ws - 「放一則訊息、等答案、讀 stack」與兩鐘期限的共用小零件：給人用的 aos-agent say／listen／chat（proto8/cmd/aos-agent；11-04 前是 extras/human 的 aos-say／aos-listen）用。

10-24 遷移（tool-lib 遷移清單「human、aos-ai 的放題、等答案合成一份」）：兩邊各寫了一份同樣的事，收到這裡；不是工具（沒有 _entry），
是 py/ 的共用模組，命令列用 realpath 找到這個資料夾再 import。
11-03 aos-ai 刪了（使用者「一起刪」），只服務它的 loop_state、tail_jsonl 跟著拿掉。純標準庫（寄信叫 PATH 上的 aos-post）。
10-30 改走 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle 結論 A-7、A-8、第 4 步）：只碰 agent 的 stack——
  ① queue＝<stack>/queue/（當 queue 用的信箱：寄的都帶 --ordered（C-54 R14）；寄＝aos-post send --ordered，一封信的 body＝一則 OpenAI message）；
  ② history＝<stack>/history.jsonl（回答＝最新那則沒有 tool_calls 的 assistant，沒有 out/）；
  ③ ctl／state＝aos-loop 開在 <stack>/ctl.json、state.json 的窗（state 的 phase 看得出 paused）。
舊協議（工作區的 new/ cur/ out/ done/，P-11：agent-bob／ann／dan、topdown 這些 fsm 範本；11-04 demo 刪了）這裡不再認。
11-03 起不讀 trace.jsonl（使用者「整個拿掉」，thinking 2026-11-03-trace）：fsm、aos-eca-turn 都不寫了，last_jsonl／unit_of／failed 跟著拿掉。"""
import json, os, re, subprocess, sys, time

import aos_flags

STAGES = ("new", "cur", "archive")           # queue 的格（11-03 aos-post 歸檔格 done/ 改名 archive/）；tmp/ 是寄到一半的，不看
ORDERED = re.compile(r"^[0-9]{12}\.")        # 有序信的名字：<12 位序號>.<尾名>（N-16）


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def _tick_decimal(text, source, positive=False):
    """只收 ASCII 十進位整數，範圍與 C++ 的 long long 相同。"""
    if not text or any(ch < "0" or ch > "9" for ch in text):
        value = -1
    else:
        try:
            value = int(text.lstrip("0") or "0")
        except ValueError:
            value = -1
    if value < (1 if positive else 0) or value > 9223372036854775807:
        kind = "positive" if positive else "non-negative"
        raise Error("TickBad", "%s must be a %s decimal integer within signed 64-bit range" % (source, kind))
    return value


def now_tick():
    """沒設 AOS_TICK＝None；缺檔 warning 每行程每路徑一次且當 0；空檔＝0；壞檔＝TickBad。"""
    path = os.environ.get("AOS_TICK")
    if not path:
        return None
    try:
        with open(path, "rb") as f:
            text = f.read().strip(b" \t\n\r\f\v").decode("ascii")
    except FileNotFoundError:
        aos_flags.warn_missing_tick(path, prog=os.path.basename(sys.argv[0]))
        return 0
    except (OSError, UnicodeError, ValueError) as e:
        raise Error("TickBad", "cannot read AOS_TICK file %s: %s" % (path, e)) from None
    return _tick_decimal(text, "AOS_TICK file") if text else 0


def tick_interval_ms():
    """AOS_TICK_INTERVAL 的正整數毫秒，沒設或空＝1000。"""
    text = os.environ.get("AOS_TICK_INTERVAL")
    return _tick_decimal(text, "AOS_TICK_INTERVAL", positive=True) if text else 1000


def utc_now_epoch_ms():
    """現在的 UTC epoch 毫秒，可寫檔跨行程比較。"""
    return time.time_ns() // 1000000


def deadline_after(ticks):
    """回 (on_tick, at)；有時鐘數 tick，否則換成 UTC epoch 毫秒。"""
    if not isinstance(ticks, int) or isinstance(ticks, bool) or not -9223372036854775808 <= ticks <= 9223372036854775807:
        raise Error("TickBad", "deadline ticks must be an integer within signed 64-bit range")
    now = now_tick()
    on_tick = now is not None
    if on_tick:
        at = now + ticks
    else:
        duration = ticks * tick_interval_ms()
        if not -9223372036854775808 <= duration <= 9223372036854775807:
            raise Error("TickBad", "deadline duration is outside signed 64-bit range")
        at = utc_now_epoch_ms() + duration
    if not -9223372036854775808 <= at <= 9223372036854775807:
        raise Error("TickBad", "deadline is outside signed 64-bit range")
    return on_tick, at


def expired(deadline):
    """依期限種類判到期；同一行程不應失去時鐘，若失去就回 False。"""
    on_tick, at = deadline
    if on_tick:
        now = now_tick()
        return now is not None and now >= at
    return utc_now_epoch_ms() >= at


def stack_of(ws, stack=None):
    """stack＝給的 ＞ $AOS_STACK ＞ <ws>/.stack/（N-57 預設，同 aos-exec）；轉絕對路徑。"""
    return os.path.abspath(stack or os.environ.get("AOS_STACK") or os.path.join(ws, ".stack"))


def box_of(stack):
    return os.path.join(stack, "queue")


def letter_key(name):
    """信件名稱的處理順序（同 aos-post sort_letters，thinking 2026-11-03-aos-post § 2）：有序（^[0-9]{12}\\.）全部在前、照名字；
    無序全部在後、照名字（預設名時間開頭＝寄出先後）。給 sorted(key=)／max(key=) 用。"""
    return (0 if ORDERED.match(name) else 1, name)


def names(stack, stage):
    """queue 某一格裡的信件名稱（. 開頭的不算，N-05）；照處理順序（letter_key）排。"""
    try:
        return sorted((n for n in os.listdir(os.path.join(box_of(stack), stage)) if not n.startswith(".")), key=letter_key)
    except (FileNotFoundError, NotADirectoryError):
        return []


def where(stack, name):
    """這封信現在在 queue 的哪幾格。"""
    if not name or "/" in name or name.startswith("."):
        return []
    return [s for s in STAGES if os.path.lexists(os.path.join(box_of(stack), s, name))]


def waiting(stack):
    """還沒答的信（cur/ 先、再 new/）。"""
    return names(stack, "cur") + names(stack, "new")


def read(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def run_post(args, stdin_text=""):
    """叫 aos-post；回 (結束碼, stdout)，stderr 原樣透出；起不來＝PostFailed。"""
    try:
        r = subprocess.run(["aos-post"] + args, input=stdin_text, stdout=subprocess.PIPE, text=True)
    except OSError as e:
        raise Error("PostFailed", "aos-post failed to start (proto8/impls/aos-post/bin must be on PATH): %s" % e)
    return r.returncode, r.stdout


def post(args, stdin_text=""):
    """叫 aos-post；回去掉頭尾空白的 stdout；退非 0＝PostFailed，原因不帶下層的話。"""
    code, out = run_post(args, stdin_text)
    if code != 0:
        raise Error("PostFailed", "aos-post %s exited %d" % (args[0], code))
    return out.strip()


def put(stack, text):
    """把一段文字變成一則 user message 寄進 <stack>/queue/（沒有 queue 就 aos-post init，寄信人先建信箱＝可以先說再跑 agent）；
    content＝文字去掉結尾的換行。回信件名稱（new/ 裡的名字，帶序號）。錯＝Error("PostFailed")。"""
    box = box_of(stack)
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        post(["init", box])
    return post(["send", "--ordered", box], json.dumps({"role": "user", "content": text.rstrip("\n")}, ensure_ascii=False))


def history(stack):
    """history.jsonl 的每一則（解不開、不是物件的那行略過）；沒有＝[]。"""
    out = []
    for line in (read(os.path.join(stack, "history.jsonl"), "") or "").splitlines():
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if isinstance(m, dict):
            out.append(m)
    return out


def is_answer(m):
    return m.get("role") == "assistant" and not m.get("tool_calls")


def text_of(m):
    c = m.get("content")
    return c if isinstance(c, str) else ("" if c is None else json.dumps(c, ensure_ascii=False))


def answers(stack):
    """history 裡每則回答（沒有 tool_calls 的 assistant）的文字，照順序。"""
    return [text_of(m) for m in history(stack) if is_answer(m)]


def exchanges(stack):
    """一問一答：[(問的那些 user 文字, 回答)]——每則回答配上它前面、上一則回答之後的 user。"""
    out, asked = [], []
    for m in history(stack):
        if m.get("role") == "user":
            asked.append(text_of(m))
        elif is_answer(m):
            out.append((asked, text_of(m)))
            asked = []
    return out
