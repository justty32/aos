"""aos_ws - 「放一則訊息、等答案、讀 stack」與兩鐘期限的共用小零件：給人用的 aos-agent say／listen／chat（proto8/cmd/aos-agent；11-04 前是 extras/human 的 aos-say／aos-listen）用。

10-24 遷移（tool-lib 遷移清單「human、aos-ai 的放題、等答案合成一份」）：兩邊各寫了一份同樣的事，收到這裡；不是工具（沒有 _entry），
是 lib/ 的共用模組，命令列用 realpath 找到這個資料夾再 import。
11-03 aos-ai 刪了（使用者「一起刪」），只服務它的 loop_state、tail_jsonl 跟著拿掉。純標準庫（寄信叫 PATH 上的 aos-post）。
10-30 改走 agent 對話協議（CONVENTION P-42；thinking 2026-10-30-agent-lifecycle 結論 A-7、A-8、第 4 步）：只碰 agent 的 stack——
  ① queue＝<stack>/queue/（當 queue 用的信箱：寄的都帶 --ordered（C-54 R14）；寄＝aos-post send --ordered，一封信的 body＝一則 OpenAI message）；
  ② history＝<stack>/history.jsonl（回答＝最新那則沒有 tool_calls 的 assistant，沒有 out/）；
  ③ ctl／state＝aos-loop 開在 <stack>/ctl.json、state.json 的窗（state 的 phase 看得出 paused）。
舊協議（工作區的 new/ cur/ out/ done/，P-11：agent-bob／ann／dan、topdown 這些 fsm 範本；11-04 demo 刪了）這裡不再認。
11-03 起不讀 trace.jsonl（使用者「整個拿掉」，thinking 2026-11-03-trace）：fsm、aos-eca-turn 都不寫了，last_jsonl／unit_of／failed 跟著拿掉。"""
import json, os, re, subprocess, sys

from aos import flags as aos_flags

STAGES = ("new", "cur", "archive")           # queue 的格（11-03 aos-post 歸檔格 done/ 改名 archive/）；tmp/ 是寄到一半的，不看
ORDERED = re.compile(r"^[0-9]{12}\.")        # 有序信的名字：<12 位序號>.<尾名>（N-16）


class Error(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


# 兩鐘期限只有 py/aos/tool_io.py 一份（11-12 收重複）；這裡只把缺檔提醒的開頭換成 argv[0] 檔名、tool_io.Error 換成本模組的 Error。
_clock = aos_flags.tool_io


def _clocked(fn, *args):
    try:
        return fn(*args)
    except _clock.Error as e:
        raise Error(e.code, str(e)) from None


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
        raise Error("PostFailed", "aos-post failed to start (proto8/bin must be on PATH): %s" % e)
    return r.returncode, r.stdout


def post(args, stdin_text=""):
    """叫 aos-post；回去掉頭尾空白的 stdout；退非 0＝PostFailed，原因不帶下層的話。"""
    code, out = run_post(args, stdin_text)
    if code != 0:
        raise Error("PostFailed", "aos-post %s exited %d" % (args[0], code))
    return out.strip()


def put(stack, text, name=None):
    """把一段文字變成一則 user message 寄進 <stack>/queue/（沒有 queue 就 aos-post init，寄信人先建信箱＝可以先說再跑 agent）；
    content＝文字去掉結尾的換行；name＝選填、寄件人（message 的 name 欄；11-13 aos-agent say 對 eca 才給）。
    回信件名稱（new/ 裡的名字，帶序號）。錯＝Error("PostFailed")。"""
    box = box_of(stack)
    if not all(os.path.isdir(os.path.join(box, s)) for s in ("tmp", "new", "cur")):
        post(["init", box])
    body = {"role": "user", "content": text.rstrip("\n")}
    if name:
        body["name"] = name
    return post(["send", "--ordered", box], json.dumps(body, ensure_ascii=False))


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


# ---- 回答配對（reply-match-1114，使用者 11-14 go: yes、land: one）----
# history 的列多一個 "aos" 物件鍵：收信的 user 列 {"aos": {"letter": 信名}}；最終回答 {"aos": {"answer_to": [信名…]}}。
# <stack>/letters.json＝{"pending": [交出去還沒答的信名…], "dropped": [{"letter", "reason", "at"}…，最多 50 筆]}，
# 只有 agent 的身體（fsm 的 idle／wait、aos-eca-turn）寫；aos-agent ask／listen 只讀。reason：bad（壞信）、blocked（hook 擋）、failed（交出去後腦失敗）。
# 寫的順序（讀的一方照信流向查，才不會有空窗）：收信＝先 letters_take、再附加 history（帶 aos.letter）、最後 done；
# 回答＝先附加 history（帶 aos.answer_to）、再 letters_answered 清 pending。aos 鍵送模型端點前一定要剝掉（for_endpoint）。
LETTERS = "letters.json"
REMOVED = "history_removed.jsonl"   # 同 py/aos/agentlib/cli_hook.py、aos_agent/history.py
DROPPED_MAX = 50
DROP_REASONS = ("bad", "blocked", "failed")


def letters(stack):
    """letters.json 的內容；沒有或壞了＝空的那份（不報錯：讀的一方要能面對還沒升級的身體）。"""
    try:
        d = json.loads(read(os.path.join(stack, LETTERS), "") or "{}")
    except ValueError:
        d = {}
    if not isinstance(d, dict):
        d = {}
    pending, dropped = d.get("pending"), d.get("dropped")
    pending = [n for n in pending if isinstance(n, str)] if isinstance(pending, list) else []
    dropped = [x for x in dropped if isinstance(x, dict) and isinstance(x.get("letter"), str)] if isinstance(dropped, list) else []
    return {"pending": pending, "dropped": dropped}


def _save_letters(stack, d):
    path = os.path.join(stack, LETTERS)
    tmp = os.path.join(stack, ".%s.%d.tmp" % (LETTERS, os.getpid()))   # 點開頭：stack.gitignore 擋得到、寫到一半也不進 git
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def letters_take(stack, names_):
    """這幾封信要交給腦了：加進 pending（照序、不重複）。在附加 history 之前叫。"""
    names_ = [n for n in names_ if isinstance(n, str) and n]
    if not names_:
        return
    d = letters(stack)
    for n in names_:
        if n not in d["pending"]:
            d["pending"].append(n)
    d["dropped"] = [x for x in d["dropped"] if x["letter"] not in names_]   # 又交出去了（例：記成 failed 後還在 cur/ 重交）＝不再算被丟
    _save_letters(stack, d)


def letters_answered(stack, names_=None):
    """最終回答寫進 history 之後叫：把這則回答的 answer_to（names_）從 pending 拿掉；names_ 是 None＝清空整個 pending（fsm：
    answer_to 本來就是寫之前用 letters_pending 拿的整份）。eca 給 Handoff.good，別輪留下的信不會被順手清掉。"""
    d = letters(stack)
    keep = [] if names_ is None else [n for n in d["pending"] if n not in names_]
    if keep != d["pending"]:
        d["pending"] = keep
        _save_letters(stack, d)


def letters_pending(stack):
    return letters(stack)["pending"]


def letters_drop(stack, names_, reason):
    """這幾封信不會有回答了：從 pending 拿掉，記進 dropped（帶原因與 UTC 時刻），只留最後 DROPPED_MAX 筆。"""
    import datetime
    names_ = [n for n in names_ if isinstance(n, str) and n]
    if not names_:
        return
    if reason not in DROP_REASONS:
        raise ValueError("reason must be one of %s" % (DROP_REASONS,))
    at = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    d = letters(stack)
    d["pending"] = [n for n in d["pending"] if n not in names_]
    d["dropped"] = (d["dropped"] + [{"letter": n, "reason": reason, "at": at} for n in names_])[-DROPPED_MAX:]
    _save_letters(stack, d)


def mark_letter(m, name):
    """收信的 user 列：拷貝一份，aos 鍵換成 {"letter": name}（信裡自帶的 aos 鍵一律蓋掉，不能偽造）。"""
    m = dict(m)
    m.pop("aos", None)
    if name:
        m["aos"] = {"letter": name}
    return m


def mark_answer(m, names_):
    """最終回答：拷貝一份，aos 鍵換成 {"answer_to": [...]}（端點回的 aos 鍵一律蓋掉）；names_ 空＝不帶 aos 鍵。"""
    m = dict(m)
    m.pop("aos", None)
    names_ = [n for n in names_ or [] if isinstance(n, str) and n]
    if names_:
        m["aos"] = {"answer_to": names_}
    return m


def for_endpoint(m):
    """送模型端點前：拷貝一份、拿掉 aos 鍵，其他鍵照留。"""
    if isinstance(m, dict) and "aos" in m:
        m = dict(m)
        m.pop("aos")
    return m


def _aos(m):
    a = m.get("aos") if isinstance(m, dict) else None
    return a if isinstance(a, dict) else {}


def _removed(stack):
    out = []
    for line in (read(os.path.join(stack, REMOVED), "") or "").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("message"), dict):
            out.append(r["message"])
    return out


def answer_for(stack, name):
    """這封信的回答到哪了。回 (狀態, 文字)：
    waiting＝還在 queue（new／cur）；answered＝history 裡有則回答的 aos.answer_to 含它（文字＝那則回答）；answered_removed＝同上、但那則在 history_removed；
    dropped＝letters.json 記它被丟（文字＝原因）；handed＝已交給腦、還沒答；unknown＝哪裡都沒有它的紀錄（舊身體，或信名寫錯）。
    查的順序照信流動的方向（queue → history → history_removed → letters.json），配合寫的一方的順序就不會有空窗。"""
    if where(stack, name) and set(where(stack, name)) & {"new", "cur"}:
        return ("waiting", "")
    handed = False
    for removed, rows in ((False, history(stack)), (True, _removed(stack))):
        for m in rows:
            a = _aos(m)
            if is_answer(m) and name in (a.get("answer_to") or []):
                return ("answered", text_of(m)) if not removed else ("answered_removed", text_of(m))
            if a.get("letter") == name:
                handed = True
    d = letters(stack)
    for x in reversed(d["dropped"]):
        if x["letter"] == name:
            return ("dropped", str(x.get("reason") or ""))
    if handed or name in d["pending"]:
        return ("handed", "")
    return ("unknown", "")
