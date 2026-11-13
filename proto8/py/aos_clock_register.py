"""aos_clock_register 時鐘登記表：時鐘檔旁的 <時鐘檔名>_register.json，每格「何時往某個 aos-post 箱子寄一封信」（每 N cycle、某 cycle 一次、牆鐘某時刻一次、cron）；aos-clock 寄、aos-clock-register 改（11-10 晚 clock-letters；11-13 線鐘 wake-timer）。
形狀：{"description": …, "letters": {名字: {排法, "box": 路徑字串或指示詞物件, "text": 非空字串, "by": 誰登記的（給人看）}}}。
排法四選一（11-13 wake-timer）："every": 正整數（cycle % every == 0，留著）｜"at_cycle": 非負整數（cycle ≥ 它寄一次、拿掉）｜
"at_time": 帶時區 ISO（牆鐘 ≥ 它寄一次、拿掉）｜"cron": 五欄＋"next": ISO（牆鐘 ≥ next 寄、next 往後推）。牆鐘只在時鐘走一格時看；
錯過的（樹睡著）醒來第一格補一次，cron 錯過多次也只一次。到期的格不論寄得到寄不到都算用掉（同 every：寄不到只 warning）。
box 相對路徑從登記表所在資料夾算；物件＝aos-directive 解（$env、$path…，cwd＝登記表所在資料夾），同 hooks／tools 的寫法。
寄的信 body 一份形狀兩邊都收：{"role": "user", "content": …}（fsm idle、aos-eca-turn 當一則 user 收進 history）＋ inbox 協議的 from／status／title／what（aos-mailbox 讀得出來）＋ cycle、register。
fire 只回提醒句子、不丟例外、不印東西：時鐘不能被登記表拖垮（壞表、寄不到＝呼叫方印 warning，時鐘照樣成功）。
自我檢查（11-10 深夜，使用者「時鐘本身會每隔一定的cycle檢查自身。」）：cycle % check_every == 0（頂層鍵 check_every，正整數，
沒寫或壞＝CHECK_EVERY）時，箱子資料夾已經不在的格拿掉、寫回表，每拿掉一格一句提醒；暫時寄不到但資料夾還在的不算、
解不開的指示詞不算（判不了就不動）。寫回前重讀一次表，只拿掉那幾格。"""
import json
import os
import re
import subprocess
import sys

import aos_flags
import aos_clock_when as when_  # 牆鐘排法（at、cron）

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
import directive_value  # noqa: E402  指示詞交給 aos-directive 解的共用版（tool_io 已由 aos_flags 載入）
sys.path.pop(0)

SUFFIX = "_register.json"
KEY = "letters"
DESCRIPTION = ("Clock register: every EVERY cycles (when the new cycle number divides by EVERY) aos-clock sends TEXT "
               "as one letter to BOX (an aos-post mailbox, e.g. an agent's queue). Edit with aos-clock-register.")
KINDS = ("every", "at_cycle", "at_time", "cron")   # 一格的排法，四選一
ONCE = ("at_cycle", "at_time")                      # 寄完拿掉的
SEND_TIMEOUT_S = 5
CHECK_EVERY = 100            # 自我檢查的預設間隔（cycle）；登記表頂層 check_every 可改
NAME_BAD = re.compile(r"[\x00-\x1f\x7f/]")
ERR_RE = re.compile(r"aos-[a-z-]+: error: (.*)\Z")


class Bad(Exception):
    """登記表讀不了或形狀不對；訊息是英文原因。"""


def path_for(clock):
    """時鐘檔 → 旁邊的登記表（同資料夾，<時鐘檔名>_register.json）。"""
    clock = os.path.abspath(clock)
    return os.path.join(os.path.dirname(clock), os.path.basename(clock) + SUFFIX)


def name_problem(name):
    if not isinstance(name, str) or not name or name.startswith(".") or NAME_BAD.search(name):
        return "a name must be non-empty, without / or control characters, and not start with ."
    return None


def entry_problem(entry):
    """一格的形狀問題（英文）；沒問題＝None。不認得的鍵不管。"""
    if not isinstance(entry, dict):
        return "must be a JSON object"
    kinds = [k for k in KINDS if k in entry]
    if len(kinds) > 1:
        return "give only one of %s (got %s)" % (", ".join(KINDS), ", ".join(kinds))
    kind = kinds[0] if kinds else "every"
    v = entry.get(kind)
    if kind == "every" and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
        return "every must be a positive integer"
    if kind == "at_cycle" and (not isinstance(v, int) or isinstance(v, bool) or v < 0):
        return "at_cycle must be a non-negative integer"
    checks = {"at_time": [("at_time", when_.parse_iso)], "cron": [("cron", when_.parse_cron), ("next", when_.parse_iso)]}
    for key, check in checks.get(kind, []):
        try:
            check(entry.get(key))
        except (ValueError, TypeError) as e:
            return "%s: %s" % (key, e)
    box = entry.get("box")
    if not ((isinstance(box, str) and box) or (isinstance(box, dict) and box)):
        return "box must be a non-empty path string or a directive object"
    if not isinstance(entry.get("text"), str) or not entry["text"].strip():
        return "text must be a non-empty string"
    return None


def load_doc(path):
    """讀整份登記表 → dict（letters 一定是物件）；不在＝{}。整份壞＝Bad。"""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        raise Bad("cannot read %s: %s" % (path, getattr(e, "strerror", None) or e))
    if not isinstance(doc, dict) or not isinstance(doc.get(KEY, {}), dict):
        raise Bad("%s must be a JSON object with %s as an object" % (path, KEY))
    return doc


def load(path):
    """讀登記表 → {名字: 格}；不在＝{}。整份壞＝Bad。單格壞不在這裡擋（fire 跳過那格、ls 照列）。"""
    return load_doc(path).get(KEY, {})


def check_every(doc):
    v = doc.get("check_every")
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else CHECK_EVERY


def save(path, letters):
    """整份寫回（同資料夾 .名.pid 暫存再改名，N-05）；頂層別的鍵（check_every…）照留。OSError 往上丟。"""
    try:
        old = load_doc(path)
    except Bad:
        old = {}
    doc = dict(old, description=old.get("description") or DESCRIPTION)
    doc[KEY] = letters
    tmp = os.path.join(os.path.dirname(path), ".%s.%d" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def stored_box(box, base):
    """人給的箱子（已轉絕對）→ 存進表的寫法：跟登記表同一個頂層資料夾＝相對登記表資料夾（整棵搬走還對），否則絕對（同 aos-post 的 reply_to）。"""
    box, base = os.path.normpath(os.path.abspath(box)), os.path.normpath(os.path.abspath(base))
    top = lambda p: p.split(os.sep)[1:2]
    return os.path.relpath(box, base) if top(box) == top(base) else box


def resolve_box(box, base, table=None):
    """表裡的 box → 絕對路徑；解不開丟 Bad。table＝登記表的路徑（給了＝指示詞裡的 #/… 取表自己，11-12 ref-hash）。"""
    if isinstance(box, dict):
        try:
            box = directive_value.resolve({"v": box}, base, table, stderr=subprocess.PIPE, timeout=SEND_TIMEOUT_S).get("v")
        except directive_value.Error as e:
            if e.returncode is not None:
                raise Bad("cannot resolve the box directive: %s" % last_error(e.stderr, "aos-directive exited %d" % e.returncode))
            if not isinstance(e.cause, ValueError):        # 起不來、逾時；印的不是 JSON＝當沒解出路徑
                raise Bad("cannot resolve the box directive: %s" % e.cause)
            box = None
        if not isinstance(box, str) or not box:
            raise Bad("the box directive did not resolve to a non-empty path")
    return os.path.normpath(box if os.path.isabs(box) else os.path.join(base, box))


def is_box(path):
    return all(os.path.isdir(os.path.join(path, d)) for d in ("tmp", "new", "cur"))


def kind(entry):
    """一格的排法（已過 entry_problem）：every、at_cycle、at_time、cron 之一。"""
    return next((k for k in KINDS if k in entry), "every")


def when(entry):
    """給 ls 看的排法一欄：every＝數字（舊輸出不變）；cycle N；at 時刻；cron 式 next 時刻。"""
    k = kind(entry) if isinstance(entry, dict) else "every"
    v = entry.get(k, "?") if isinstance(entry, dict) else "?"
    if k == "every":
        return str(v)
    if k == "at_cycle":
        return "cycle %s" % v
    if k == "at_time":
        return "at %s" % v
    return "cron %s next %s" % (v, entry.get("next", "?"))


def body(name, text, cycle, due=None, now=None):
    """一封信的 body：fsm／eca 的 queue 收 role＋content，aos-mailbox 讀 from／status／title／what。due＝牆鐘排法的到期時刻（多帶 due 鍵與晚了多久）。"""
    head = "cycle %d" % cycle
    if due is not None:
        head += ", due %s" % when_.show(due)
        late = when_.late(due, now or when_.now())
        head += " (%s)" % late if late else ""
    doc = {"role": "user", "content": aos_flags.aos_note("clock", "%s. %s" % (head, text)),
           "from": "clock", "status": "PROGRESS", "title": "clock cycle %d: %s" % (cycle, name), "what": text,
           "cycle": cycle, "register": name}
    if due is not None:
        doc["due"] = when_.fmt(due)
    return doc


def last_error(stderr, fallback):
    lines = [m.group(1) for m in map(ERR_RE.match, (stderr or "").splitlines()) if m]
    return lines[-1] if lines else fallback


def send(box, doc):
    """aos-post send BOX < doc；成功回 None，失敗回英文原因。"""
    try:
        r = subprocess.run(["aos-post", "send", box], input=json.dumps(doc, ensure_ascii=False), capture_output=True,
                           text=True, timeout=SEND_TIMEOUT_S)
    except OSError as e:
        return "aos-post cannot start (must be on PATH): %s" % e
    except subprocess.TimeoutExpired:
        return "aos-post send took over %d s" % SEND_TIMEOUT_S
    return None if r.returncode == 0 else last_error(r.stderr, "aos-post send exited %d" % r.returncode)


def due_at(entry, cycle, now):
    """這格這一格該不該寄：(該寄, 牆鐘到期時刻或 None)。"""
    k = kind(entry)
    if k == "every":
        return cycle % entry["every"] == 0, None
    if k == "at_cycle":
        return cycle >= entry["at_cycle"], None
    t = when_.parse_iso(entry["at_time"] if k == "at_time" else entry["next"])
    return now >= t, t


def fire(clock, cycle, now=None):
    """時鐘剛寫進 cycle：登記表裡到期的格各寄一封（every：cycle % every == 0；at_cycle／at_time／cron 見檔頭）。
    一次性的寄完拿掉、cron 的 next 往後推（寫回）。回提醒句子的清單（空＝沒事或沒登記表）。不丟例外。now＝牆鐘（測試用）。"""
    path = path_for(clock)
    if not os.path.lexists(path):
        return []
    try:
        doc = load_doc(path)
    except Bad as e:
        return ["clock register skipped: %s" % e]
    now = now or when_.now()
    letters = doc.get(KEY, {})
    base = os.path.dirname(path)
    warnings = []
    used = {}                                      # 名字 → 寄時的那格（一次性、cron：寫回用）
    if cycle % check_every(doc) == 0:
        letters = dict(letters)
        warnings += self_check(path, letters, base)
    for name in sorted(letters):
        entry = letters[name]
        why = name_problem(name) or entry_problem(entry)
        if why:
            warnings.append("clock register entry %r skipped: %s" % (name, why))
            continue
        go, due = due_at(entry, cycle, now)
        if not go:
            continue
        if kind(entry) != "every":
            used[name] = entry                     # 寄得到寄不到都算用掉（同 every：寄不到只提醒一次）
        try:
            box = resolve_box(entry["box"], base, path)
        except Bad as e:
            warnings.append("clock register entry %s: %s" % (name, e))
            continue
        why = send(box, body(name, entry["text"], cycle, due, now))
        if why:
            warnings.append("clock register entry %s: cannot send to %s: %s" % (name, box, why))
    if used:
        warnings += write_back(path, used, now)
    return warnings


def write_back(path, used, now):
    """寄過的一次性格拿掉、cron 格的 next 推到 now 之後；寫回前重讀，只動內容跟寄時一樣的格（別人剛換掉的不動）。回提醒句子。"""
    out = []
    try:
        fresh = load(path)
        for name, entry in used.items():
            if fresh.get(name) != entry:
                continue
            if kind(entry) in ONCE:
                del fresh[name]
                continue
            try:
                fresh[name] = dict(entry, next=when_.fmt(when_.cron_next(entry["cron"], now)))
            except ValueError as e:
                del fresh[name]
                out.append("clock register: removed entry %s: %s" % (name, e))
        save(path, fresh)
    except (Bad, OSError) as e:
        out.append("clock register: cannot write back %s (one-time entries stay, cron next not moved): %s"
                   % (path, getattr(e, "strerror", None) or e))
    return out


def self_check(path, letters, base):
    """箱子資料夾已經不在的格從 letters 拿掉並寫回表；回提醒句子。寫不回＝提醒、這次照樣不寄給它們。"""
    gone = {}
    for name, entry in letters.items():
        if name_problem(name) or entry_problem(entry):
            continue
        try:
            box = resolve_box(entry["box"], base, path)
        except Bad:
            continue                               # 判不了就不動
        if not os.path.isdir(box):
            gone[name] = (box, entry.get("by") or "?")
    if not gone:
        return []
    for name in gone:
        letters.pop(name, None)
    out = ["clock register: removed entry %s (added by %s): its box %s no longer exists" % (n, by, b)
           for n, (b, by) in sorted(gone.items())]
    try:
        fresh = load(path)                         # 寫回前重讀，只拿掉那幾格（別人剛加的不蓋掉）
        for name in gone:
            fresh.pop(name, None)
        save(path, fresh)
    except (Bad, OSError) as e:
        out.append("clock register: cannot write back the cleaned register %s: %s" % (path, getattr(e, "strerror", None) or e))
    return out

