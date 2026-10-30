"""aos_ws - 「放一則訊息、等答案、讀 stack」的共用小零件：給人用的 aos-say／aos-listen／aos-chat（proto8/extras/human）與給 AI 用的 aos-ai（proto8/extras/ai_tools）一起用。

10-24 遷移（tool-lib 遷移清單「human、aos-ai 的放題、等答案合成一份」）：兩邊各寫了一份同樣的事，收到這裡；不是工具（沒有 _entry），
是 lib/aos 的共用模組，兩支命令列用 realpath 找到這個資料夾再 import。純標準庫（寄信叫 PATH 上的 aos-post）。
10-30 改走 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle 結論 A-7、A-8、第 4 步）：只碰 agent 的 stack——
  ① queue＝<stack>/queue/（N-16 有順序的信箱；寄＝aos-post send --ordered，一封信的 body＝一則 OpenAI message）；
  ② history＝<stack>/history.jsonl（回答＝最新那則沒有 tool_calls 的 assistant，沒有 out/）；
  ③ ctl／state＝aos-loop 開在 <stack>/ctl.json、state.json 的窗（state 的 phase 看得出 paused）。
舊協議（工作區的 new/ cur/ out/ done/，P-11 的 10-30 改口：agent-bob／ann／dan、topdown 這些 fsm 範本）這裡不再認。
stack 裡 fsm 每格一行 trace.jsonl（P-07；aos-round 也是這種）、eca turn 與 10-30 前的舊 round 每格一行（unit）這裡只讀不改。"""
import json, os, subprocess

STAGES = ("new", "cur", "done")              # queue 的格；tmp/ 是寄到一半的，不看


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def stack_of(ws, stack=None):
    """stack＝給的 ＞ $AOS_STACK ＞ <ws>/.stack/（N-57 預設，同 aos-exec）；轉絕對路徑。"""
    return os.path.abspath(stack or os.environ.get("AOS_STACK") or os.path.join(ws, ".stack"))


def box_of(stack):
    return os.path.join(stack, "queue")


def names(stack, stage):
    """queue 某一格裡的信號（. 開頭的不算，N-05）；照名字排序＝寄的順序。"""
    try:
        return sorted(n for n in os.listdir(os.path.join(box_of(stack), stage)) if not n.startswith("."))
    except (FileNotFoundError, NotADirectoryError):
        return []


def where(stack, sig):
    """這封信現在在 queue 的哪幾格。"""
    if not sig or "/" in sig or sig.startswith("."):
        return []
    return [s for s in STAGES if os.path.lexists(os.path.join(box_of(stack), s, sig))]


def waiting(stack):
    """還沒答的信（cur/ 先、再 new/）。"""
    return names(stack, "cur") + names(stack, "new")


def read(path, default=None):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return default


def post(args, stdin_text=""):
    try:
        r = subprocess.run(["aos-post"] + args, input=stdin_text, capture_output=True, text=True)
    except OSError as e:
        raise Error("PostFailed", "aos-post 起不來（PATH 上要有 proto8/impls/aos-post/bin）：%s" % e)
    if r.returncode != 0:
        raise Error("PostFailed", "aos-post %s 退 %d：%s" % (args[0], r.returncode, r.stderr.strip()))
    return r.stdout.strip()


def put(stack, text):
    """把一段文字變成一則 user message 寄進 <stack>/queue/（沒有 queue 就 aos-post init，寄信人先建信箱＝可以先說再跑 agent）；
    content＝文字去掉結尾的換行。回信號（new/ 裡的名字，帶序號）。錯＝Error("PostFailed")。"""
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


def loop_state(stack):
    """aos-loop 的 state 窗（<stack>/state.json）；沒有或讀不懂＝None。"""
    try:
        st = json.loads(read(os.path.join(stack, "state.json"), "") or "null")
    except ValueError:
        return None
    return st if isinstance(st, dict) else None


def tail_jsonl(path, n):
    """一份 .jsonl 最後 n 行（解不開的那行放 {"bad_line": 前 200 字}）；檔不在＝[]。"""
    text = read(path)
    if text is None:
        return []
    lines = [l for l in text.splitlines() if l.strip()]
    rows = []
    for l in lines[-n:] if n > 0 else []:
        try:
            rows.append(json.loads(l))
        except ValueError:
            rows.append({"bad_line": l[:200]})
    return rows


def last_jsonl(path):
    """一份 .jsonl 最後一行解得開的；沒有＝None（stack 的 trace.jsonl 看最後一格用）。"""
    for line in reversed((read(path, "") or "").splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def unit_of(t):
    """trace 一行是哪一格：fsm（含 aos-round）寫 state；eca turn 與 10-30 前的舊 round 寫 unit（舊 stack 還讀得到）。"""
    return t.get("unit") or t.get("state") or "?"


def failed(t):
    """trace 那一行是不是失敗（非 0、非 10，或被訊號停掉）。"""
    return bool(t) and (t.get("code") not in (0, 10) or t.get("signal") is not None)
