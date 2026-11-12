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
import json, os, re, subprocess, sys

import aos_flags

STAGES = ("new", "cur", "archive")           # queue 的格（11-03 aos-post 歸檔格 done/ 改名 archive/）；tmp/ 是寄到一半的，不看
ORDERED = re.compile(r"^[0-9]{12}\.")        # 有序信的名字：<12 位序號>.<尾名>（N-16）


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# 兩鐘期限只有 lib/tool_io.py 一份（11-12 收重複）；這裡只把缺檔提醒的開頭換成 argv[0] 檔名、tool_io.Error 換成本模組的 Error。
_clock = aos_flags.tool_io
utc_now_epoch_ms = _clock.utc_now_epoch_ms


def _clocked(fn, *args):
    try:
        return fn(*args)
    except _clock.Error as e:
        raise Error(e.code, str(e)) from None


def now_cycle():
    """沒設 AOS_CLOCK＝None；缺檔 warning 每行程每路徑一次且當 0；空檔＝0；壞檔＝ClockBad。"""
    return _clocked(_clock.now_cycle, os.path.basename(sys.argv[0]))


def clock_interval_ms():
    """AOS_CLOCK_INTERVAL 的正整數毫秒，沒設或空＝1000。"""
    return _clocked(_clock.clock_interval_ms)


def deadline_after(cycles):
    """回 (on_clock, at)；有時鐘數 cycle，否則換成 UTC epoch 毫秒。"""
    return _clocked(_clock.deadline_after, cycles, os.path.basename(sys.argv[0]))


def expired(deadline):
    """依期限種類判到期；同一行程不應失去時鐘，若失去就回 False。"""
    return _clocked(_clock.expired, deadline, os.path.basename(sys.argv[0]))


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


# 同一路徑的壞行只提醒一次；fork 後各行程分開計算。
_history_warnings = set()


def history(stack):
    """history.jsonl 的每一則（解不開、不是物件的那行提醒一次後略過）；沒有＝[]。"""
    out = []
    path = os.path.join(stack, "history.jsonl")
    for number, line in enumerate((read(path, "") or "").splitlines(), 1):
        try:
            m = json.loads(line)
        except ValueError:
            m = None
        if isinstance(m, dict):
            out.append(m)
        else:
            key = (os.getpid(), os.path.abspath(path))
            if key not in _history_warnings:
                _history_warnings.add(key)
                aos_flags.warn(os.path.basename(sys.argv[0]),
                               "history.jsonl line %d is not a JSON object; skipped it" % number)
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
