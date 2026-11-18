"""board - 布告欄 board/1：<stack>/board.json 的讀（重試一次）、算「現在算數的狀態」四步、寫（鎖＋暫存檔改名）與 set／clear／wait 三種改法。

圖紙：02 稿 §2、§7；05 A7（沒寫 expires_at 的一律 updated_at＋24h 過期，不分 mode）、A13（flock <root>/comm/board.lock、暫存檔名帶 pid）、
A14（四步＝讀檔→時鐘校正→過期→併機器事實）、P1（waiting_on 項可帶 level、notified_at）。
未知鍵：讀的人忽略、寫的人保留（set／clear 只換 board/1 認得的欄位，其餘照搬；ext 也照搬）。"""
import contextlib
import datetime
import fcntl
import json
import os
import time

from . import Fail, LEVELS
from . import times

FORMAT = "board/1"
FILE = "board.json"
LOCK = os.path.join("comm", "board.lock")      # 05 A2：帳本與鎖都在 <root>/comm/
MODES = ("here", "busy", "dnd", "away")
ACCEPTS = ("low", "normal", "urgent", "none")
BYS = ("self", "auto", "user")
ASLEEP = ("sleeping", "stopped")                # phase 是這兩個＝不在（四步第 4 步）
# set 會整張換掉的欄位（board/1 認得的）；不在這裡的鍵（含 ext）寫的時候照搬
KNOWN = ("format", "seq", "updated_at", "by", "mode", "text", "doing", "waiting_on", "back_at", "back_text",
         "expires_at", "accept", "allow_from", "wake_on_urgent", "clear_on_start", "deputy")
DEFAULT_FOR = {"dnd": datetime.timedelta(hours=2), "away": datetime.timedelta(hours=12)}   # 沒給到期時的預設
STALE_AFTER = datetime.timedelta(hours=24)
CLOCK_SLACK = datetime.timedelta(minutes=5)
MAX = {"text": 1000, "doing": 200, "back_text": 100}
MAX_WHAT = 200                                  # waiting_on 每筆的 what
MAX_WAITING = 20
MAX_BYTES = 16 * 1024


def path_of(root):
    return os.path.join(root, FILE)


# ---- 讀 ------------------------------------------------------------------------------

def _problem(v):
    """board/1 的最低要求（讀的人用）：物件、format、mode、updated_at；不合＝原因字串，合＝None。"""
    if not isinstance(v, dict):
        return "not a JSON object"
    if v.get("format") != FORMAT:
        return "format is not %s" % FORMAT
    if v.get("mode") not in MODES:
        return "mode is not one of %s" % ", ".join(MODES)
    if times.parse(v.get("updated_at")) is None:
        return "updated_at is not an ISO 8601 time"
    return None


def load(root):
    """(布告欄 dict 或 None, 問題 或 None)。沒有檔＝(None, None)，是常態；讀不了、JSON 壞、不合 board/1＝重試一次，
    還是不行＝(None, 原因)，讀的人當沒貼（四步第 1 步）。"""
    path = path_of(root)
    problem = None
    for attempt in range(2):
        try:
            with open(path, encoding="utf-8") as fh:
                v = json.load(fh)
        except FileNotFoundError:
            return None, None
        except OSError as e:
            problem = "cannot read it: %s" % (e.strerror or e)
        except (ValueError, UnicodeError):
            problem = "not valid JSON"
        else:
            problem = _problem(v)
            if problem is None:
                return v, None
        if not attempt:
            time.sleep(0.05)
    return None, problem


def effective(board, now=None, live=None, problem=None):
    """四步（06 §7.3）算完的結果：
    {"board": 原樣或 None, "problem"?, "mode": 算數的 mode, "posted", "stale", "clock_odd", "overdue", "asleep",
     "waiting_on": 算數的等待（過期＝空）, "live": live 或 None}。
    live＝daemon 表那一列的 {"phase", "busy"}（查不到＝None，就不併）。"""
    now = now or times.now()
    out = {"board": board, "mode": "here", "posted": board is not None, "stale": False, "clock_odd": False,
           "overdue": False, "asleep": False, "waiting_on": [], "live": live}
    if problem:
        out["problem"] = problem
    if board is not None:
        updated = times.parse(board.get("updated_at")) or now
        if updated > now + CLOCK_SLACK:                          # 第 2 步：時鐘校正
            out["clock_odd"] = True
            updated = now
        expires = times.parse(board.get("expires_at"))
        out["stale"] = now > expires if expires is not None else now > updated + STALE_AFTER   # 第 3 步（A7：不分 mode）
        if not out["stale"]:
            out["mode"] = board.get("mode") if board.get("mode") in MODES else "here"
            out["waiting_on"] = waiting(board)
            back = times.parse(board.get("back_at"))
            out["overdue"] = back is not None and now > back
    if isinstance(live, dict) and live.get("phase") in ASLEEP:   # 第 4 步：事實優先
        out["asleep"] = True
        out["mode"] = "away"
    return out


def waiting(board):
    """waiting_on 裡認得的項（物件、who 是不空字串）；別的忽略。"""
    items = board.get("waiting_on") if isinstance(board, dict) else None
    if not isinstance(items, list):
        return []
    return [w for w in items if isinstance(w, dict) and isinstance(w.get("who"), str) and w["who"]]


# ---- 寫 ------------------------------------------------------------------------------

@contextlib.contextmanager
def _locked(root):
    """flock <root>/comm/board.lock（沒有 comm/ 就建）；讀改寫整段拿著。"""
    try:
        os.makedirs(os.path.join(root, "comm"), exist_ok=True)
        fd = os.open(os.path.join(root, LOCK), os.O_RDWR | os.O_CREAT, 0o644)
    except OSError as e:
        raise Fail("WriteFailed", "cannot open the board lock in %s: %s" % (root, e.strerror or e))
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _raw(root):
    """寫之前讀舊的：合 board/1 的才算（不合＝當沒有、從空的開始）；waiting_on 裡不合 schema 的項丟掉，別人寫壞的一筆不擋我寫。"""
    v, _ = load(root)
    if v is None or "waiting_on" not in v:
        return v
    good = []
    for item in v["waiting_on"] if isinstance(v["waiting_on"], list) else []:
        try:
            _check_wait(item)
        except Fail:
            continue
        good.append(item)
    v = {k: x for k, x in v.items() if k != "waiting_on"}
    if good:
        v["waiting_on"] = good[-MAX_WAITING:]
    return v


def _ordered(b):
    """固定鍵的順序（format、seq、updated_at、by、mode、其餘照 KNOWN、未知鍵最後），給人看比較好讀。"""
    out = {k: b[k] for k in KNOWN if k in b}
    out.update((k, v) for k, v in b.items() if k not in out)
    return out


def check(b):
    """寫之前自己驗一次（跟 schema/comm/1/board.json 同一套限制）；不合＝ArgumentsBad／BoardFull／BoardTooBig。"""
    if b.get("mode") not in MODES:
        raise Fail("ArgumentsBad", "mode must be one of %s, not %r" % (", ".join(MODES), b.get("mode")))
    if b.get("by") not in BYS:
        raise Fail("ArgumentsBad", "by must be one of %s, not %r" % (", ".join(BYS), b.get("by")))
    if "accept" in b and b["accept"] not in ACCEPTS:
        raise Fail("ArgumentsBad", "accept must be one of %s, not %r" % (", ".join(ACCEPTS), b["accept"]))
    for k, n in MAX.items():
        if k in b and (not isinstance(b[k], str) or len(b[k]) > n):
            raise Fail("ArgumentsBad", "%s must be a string of at most %d characters" % (k, n))
    if "deputy" in b and (not isinstance(b["deputy"], str) or not b["deputy"]):
        raise Fail("ArgumentsBad", "deputy must be a non-empty name")
    if "allow_from" in b and (not isinstance(b["allow_from"], list)
                              or not all(isinstance(x, str) and x for x in b["allow_from"])):
        raise Fail("ArgumentsBad", "allow_from must be a list of names")
    for k in ("wake_on_urgent", "clear_on_start"):
        if k in b and not isinstance(b[k], bool):
            raise Fail("ArgumentsBad", "%s must be true or false" % k)
    for k in ("back_at", "expires_at", "updated_at"):
        if k in b and not times.is_time(b[k]):
            raise Fail("ArgumentsBad", "%s must be an ISO 8601 time with a zone" % k)
    if "ext" in b and not isinstance(b["ext"], dict):
        raise Fail("ArgumentsBad", "ext must be an object")
    w = b.get("waiting_on")
    if w is not None:
        if not isinstance(w, list):
            raise Fail("ArgumentsBad", "waiting_on must be a list")
        if len(w) > MAX_WAITING:
            raise Fail("BoardFull", "waiting_on holds at most %d entries; remove one with done first" % MAX_WAITING)
        for item in w:
            _check_wait(item)
    size = len(json.dumps(b, ensure_ascii=False, indent=1).encode("utf-8"))
    if size > MAX_BYTES:
        raise Fail("BoardTooBig", "the board would be %d bytes; at most %d" % (size, MAX_BYTES))


def _check_wait(item):
    """waiting_on 的一筆（schema：who、what、since_at 必有；ref、level、notified_at 選填；別的鍵照留）。"""
    if not isinstance(item, dict) or not isinstance(item.get("who"), str) or not item["who"]:
        raise Fail("ArgumentsBad", "each waiting_on entry needs who (a proc name or user)")
    if not isinstance(item.get("what"), str) or len(item["what"]) > MAX_WHAT:
        raise Fail("ArgumentsBad", "waiting_on what must be a string of at most %d characters" % MAX_WHAT)
    if not times.is_time(item.get("since_at")) or ("notified_at" in item and not times.is_time(item["notified_at"])):
        raise Fail("ArgumentsBad", "waiting_on since_at and notified_at must be ISO 8601 times with a zone")
    if "level" in item and item["level"] not in LEVELS:
        raise Fail("ArgumentsBad", "waiting_on level must be one of %s" % ", ".join(LEVELS))
    if "ref" in item and not isinstance(item["ref"], str):
        raise Fail("ArgumentsBad", "waiting_on ref must be a letter name (a string)")


def _write(root, b):
    """暫存檔 board.json.tmp.<pid>＋rename（讀的人永遠讀到完整的一份）。"""
    final = path_of(root)
    tmp = "%s.tmp.%d" % (final, os.getpid())
    data = json.dumps(b, ensure_ascii=False, indent=1) + "\n"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, final)
    except OSError as e:
        raise Fail("WriteFailed", "cannot write %s: %s" % (final, e.strerror or e))


def update(root, change, by="self", now=None):
    """鎖著讀舊的 → change(舊的 dict 或 None, now) 回新的欄位（回 None＝不寫）→ 補 format、seq＋1、updated_at、by → 驗 → 寫。
    回 (寫好的整張 或 None, 舊的)。root 不是資料夾＝StackMissing。"""
    if not os.path.isdir(root):
        raise Fail("StackMissing", "stack folder not found: %s" % root)
    if by not in BYS:
        raise Fail("ArgumentsBad", "by must be one of %s, not %r" % (", ".join(BYS), by))
    now = now or times.now()
    with _locked(root):
        old = _raw(root)
        new = change(old, now)
        if new is None:
            return None, old
        seq = old.get("seq") if old else None
        new = dict(new, format=FORMAT, updated_at=times.fmt(now), by=by,
                   seq=(seq if isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0 else 0) + 1)
        new = _ordered(new)
        check(new)
        _write(root, new)
    return new, old


def _kept(old):
    """set／clear 照搬的：board/1 不認得的鍵（含 ext）。"""
    return {k: v for k, v in (old or {}).items() if k not in KNOWN}


def set_board(root, mode, fields=None, by="self", now=None):
    """整張換掉（02 §5.1）：沒給的 board/1 欄位清空，waiting_on 例外、保留；dnd 沒給到期＝2 小時、away＝12 小時。
    fields＝{text, doing, back_at, back_text, expires_at, accept, allow_from, wake_on_urgent, clear_on_start, deputy}
    （值已是寫進檔的樣子，時間是字串）。回寫好的整張。"""
    fields = {k: v for k, v in (fields or {}).items() if v is not None}
    bad = [k for k in fields if k not in KNOWN or k in ("format", "seq", "updated_at", "by", "mode", "waiting_on")]
    if bad:
        raise Fail("ArgumentsBad", "set does not take %s" % ", ".join(sorted(bad)))
    if mode not in MODES:
        raise Fail("ArgumentsBad", "mode must be one of %s, not %r" % (", ".join(MODES), mode))

    def change(old, now):
        b = _kept(old)
        if old and isinstance(old.get("waiting_on"), list):
            b["waiting_on"] = old["waiting_on"]
        b["mode"] = mode
        b.update(fields)
        if mode in DEFAULT_FOR and "expires_at" not in b:
            b["expires_at"] = times.fmt(now + DEFAULT_FOR[mode])
        return b

    return update(root, change, by, now)[0]


def clear(root, by="self", now=None):
    """撕掉：mode here、清文字與等待（未知鍵照搬）。"""
    return update(root, lambda old, now: dict(_kept(old), mode="here"), by, now)[0]


def wait_add(root, who, what, ref=None, level=None, by="self", now=None):
    """waiting_on 加一筆 {who, what, since_at[, ref][, level]}；沒有布告欄＝先當 mode here。滿 20 筆＝BoardFull。"""
    if not isinstance(who, str) or not who.strip():
        raise Fail("ArgumentsBad", "who must be a proc name or user")
    if not isinstance(what, str) or not what.strip():
        raise Fail("ArgumentsBad", "what must say what you wait for (one line)")
    if level is not None and level not in LEVELS:
        raise Fail("ArgumentsBad", "level must be one of %s" % ", ".join(LEVELS))

    def change(old, now):
        b = dict(old) if old else {"mode": "here"}
        items = list(old.get("waiting_on")) if old and isinstance(old.get("waiting_on"), list) else []
        item = {"who": who.strip(), "what": " ".join(what.split()), "since_at": times.fmt(now)}
        if ref:
            item["ref"] = ref
        if level:
            item["level"] = level
        items.append(item)
        b["waiting_on"] = items
        return b

    return update(root, change, by, now)[0]


def wait_done(root, who, by="self", now=None):
    """拿掉 waiting_on 裡 who 的每一筆。回 (寫好的整張, 拿掉幾筆)；一筆都沒有＝(None, 0)、不寫。"""
    removed = []

    def change(old, now):
        items = old.get("waiting_on") if old else None
        if not isinstance(items, list):
            return None
        keep = [w for w in items if not (isinstance(w, dict) and w.get("who") == who)]
        if len(keep) == len(items):
            return None
        removed.append(len(items) - len(keep))
        b = dict(old)
        if keep:
            b["waiting_on"] = keep
        else:
            b.pop("waiting_on")
        return b

    new, _ = update(root, change, by, now)
    return new, (removed[0] if removed else 0)
