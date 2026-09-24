"""kernel 帳本第 3 版：K/ledger.sqlite（spec/kernel/ledger.md；2026-09-24 one-boot）。

kernel 的家是唯一放寬「四樣檔」的家：帳本不是 state.json，是一個 sqlite 檔；requests／responses／pools 仍是檔案。
tick 照舊整份讀進記憶體（跟第 2 版同形的 dict），存檔時**只寫有變的列、一次一筆交易**；崩在交易中間＝整筆沒發生。

表：
  meta(key, value)                 小鍵，value 是 JSON（chain、phase、last_seq、出貨箱、ready／delayed…）
  procs(name, status, pool, body)  一個行程一列，body＝跟第 2 版 procs.<名> 同形的 JSON
  pools(name, body)                一個池一列
  busy(cpu, ord, proc, body)       一顆忙的 cpu 一列；ord 保住插入順序（巡檢輪轉靠它）

`on`（行程 → 在哪顆）不存，讀的時候從 busy 反推。讀的人（ls、proc、agent）只 SELECT，WAL 讓讀不擋寫。
"""
import json
import os
from pathlib import Path
import sqlite3

import aos_home

LEDGER = "ledger.sqlite"
LEGACY = "state.json"
VERSION = 3
TABLES = ("procs", "pools", "busy")
SCHEMA = """
CREATE TABLE IF NOT EXISTS meta  (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS procs (name TEXT PRIMARY KEY, status TEXT, pool TEXT, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pools (name TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS busy  (cpu TEXT PRIMARY KEY, ord INTEGER NOT NULL, proc TEXT, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS busy_proc ON busy(proc);
CREATE INDEX IF NOT EXISTS busy_ord ON busy(ord);
"""


class LedgerError(aos_home.HomeError):
    pass


def path_of(home):
    return Path(home) / LEDGER


def exists(home):
    return path_of(home).is_file()


def legacy(home):
    """還是第 2 版（K/state.json）、沒換過 sqlite 的家。"""
    return not exists(home) and (Path(home) / LEGACY).is_file()


def _dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _connect(home, create=False):
    path = path_of(home)
    if not create and not path.is_file():
        raise LedgerError("NotBooted", "沒有帳本：%s（還沒 boot 過；aos up 或 aos-kernel boot）" % path)
    uri = "file:%s?mode=%s" % (path.absolute().as_posix().replace("?", "%3f").replace("#", "%23"),
                               "rwc" if create else "rw")
    try:
        conn = sqlite3.connect(uri, uri=True, isolation_level=None, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        if create:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error as exc:
        raise LedgerError("ReadFailed", "帳本打不開：%s（%s）" % (path, exc)) from exc
    return conn


def _rows(conn):
    """讀全部列：回 (state dict, 原樣的列文字) —— 後者給存檔時比對「哪些列變了」。"""
    orig = {"meta": {}, "procs": {}, "pools": {}, "busy": {}}
    state = {}
    for key, value in conn.execute("SELECT key, value FROM meta"):
        orig["meta"][key] = value
        state[key] = json.loads(value)
    procs = state["procs"] = {}
    for name, body in conn.execute("SELECT name, body FROM procs ORDER BY rowid"):
        orig["procs"][name] = body
        procs[name] = json.loads(body)
    pools = state["pools"] = {}
    for name, body in conn.execute("SELECT name, body FROM pools ORDER BY rowid"):
        orig["pools"][name] = body
        pools[name] = json.loads(body)
    busy = state["busy"] = {}
    for cpu, order, body in conn.execute("SELECT cpu, ord, body FROM busy ORDER BY ord"):
        orig["busy"][cpu] = (order, body)
        busy[cpu] = json.loads(body)
    state["on"] = {slot["proc"]: cpu for cpu, slot in busy.items() if isinstance(slot, dict)}
    return state, orig


class Store:
    """tick 與 boot 用的讀寫連線：load() 整份讀、save(state) 只寫變了的列、一筆交易。"""

    def __init__(self, home, create=False):
        self.home = Path(home).absolute()
        self.conn = _connect(self.home, create=create)
        self.orig = {"meta": {}, "procs": {}, "pools": {}, "busy": {}}

    def close(self):
        self.conn.close()

    def load(self):
        try:
            self.conn.execute("BEGIN")
            try:
                state, self.orig = _rows(self.conn)
            finally:
                self.conn.execute("COMMIT")
        except (sqlite3.Error, ValueError) as exc:
            raise LedgerError("ReadFailed", "帳本讀不懂：%s（%s）" % (path_of(self.home), exc)) from exc
        if state.get("version") not in (None, VERSION):
            raise LedgerError("LedgerVersion", "帳本版本 %r 不認得（這支 kernel 只認第 %d 版）" % (state.get("version"), VERSION))
        return state

    def _busy_rows(self, busy):
        """busy 的順序用 ord 保住：原有的 ord 還遞增就沿用，否則給一個比目前都大的新號（巡檢把前幾顆搬到尾巴＝只改那幾列）。"""
        top = max((o for o, _ in self.orig["busy"].values()), default=0)
        last, out = None, {}
        for cpu, slot in busy.items():
            old = self.orig["busy"].get(cpu)
            order = old[0] if old is not None and (last is None or old[0] > last) else None
            if order is None:
                top += 1
                order = top
            last = order
            out[cpu] = (order, _dumps(slot))
        return out

    def save(self, state):
        meta = {k: _dumps(v) for k, v in state.items() if k not in TABLES and k != "on"}
        meta["version"] = _dumps(VERSION)
        new = {"meta": meta,
               "procs": {n: _dumps(p) for n, p in state.get("procs", {}).items()},
               "pools": {n: _dumps(p) for n, p in state.get("pools", {}).items()},
               "busy": self._busy_rows(state.get("busy", {}))}
        c = self.conn
        try:
            c.execute("BEGIN IMMEDIATE")
            try:
                for key, value in meta.items():
                    if self.orig["meta"].get(key) != value:
                        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, value))
                for key in self.orig["meta"].keys() - meta.keys():
                    c.execute("DELETE FROM meta WHERE key=?", (key,))
                for name, body in new["procs"].items():
                    if self.orig["procs"].get(name) != body:
                        proc = state["procs"][name]
                        status = proc.get("status") if isinstance(proc, dict) else None
                        pool = proc.get("pool") if isinstance(proc, dict) else None
                        c.execute("INSERT INTO procs(name, status, pool, body) VALUES(?, ?, ?, ?) "
                                  "ON CONFLICT(name) DO UPDATE SET status=excluded.status, pool=excluded.pool, "
                                  "body=excluded.body", (name, status, pool, body))
                for name in self.orig["procs"].keys() - new["procs"].keys():
                    c.execute("DELETE FROM procs WHERE name=?", (name,))
                for name, body in new["pools"].items():
                    if self.orig["pools"].get(name) != body:
                        c.execute("INSERT INTO pools(name, body) VALUES(?, ?) "
                                  "ON CONFLICT(name) DO UPDATE SET body=excluded.body", (name, body))
                for name in self.orig["pools"].keys() - new["pools"].keys():
                    c.execute("DELETE FROM pools WHERE name=?", (name,))
                for cpu, (order, body) in new["busy"].items():
                    if self.orig["busy"].get(cpu) != (order, body):
                        slot = state["busy"][cpu]
                        c.execute("INSERT OR REPLACE INTO busy(cpu, ord, proc, body) VALUES(?, ?, ?, ?)",
                                  (cpu, order, slot.get("proc") if isinstance(slot, dict) else None, body))
                for cpu in self.orig["busy"].keys() - new["busy"].keys():
                    c.execute("DELETE FROM busy WHERE cpu=?", (cpu,))
                crash_hook("before-commit", state)
            except BaseException:
                c.execute("ROLLBACK")
                raise
            c.execute("COMMIT")
        except sqlite3.Error as exc:
            raise LedgerError("WriteFailed", "帳本寫不進去：%s（%s）" % (path_of(self.home), exc)) from exc
        self.orig = new


def crash_hook(where, state=None):
    """測試用掛鉤（產品路徑什麼都不做，只多讀一次環境變數）：
    AOS_KERNEL_CRASH_AT=before-commit、AOS_KERNEL_CRASH_PROC=<行程名>、AOS_KERNEL_CRASH_FLAG=<檔>：
    這筆交易要寫進那個行程、而且 FLAG 檔還不在 → 寫 FLAG（內容是 pid）後睡著，等外面 kill -9。一次性。"""
    if os.environ.get("AOS_KERNEL_CRASH_AT") != where:
        return
    flag, name = os.environ.get("AOS_KERNEL_CRASH_FLAG"), os.environ.get("AOS_KERNEL_CRASH_PROC")
    if not flag or os.path.exists(flag) or name not in ((state or {}).get("procs") or {}):
        return
    Path(flag).write_text(str(os.getpid()))
    import time
    while True:
        time.sleep(1)


# ---- 給外面讀的（ls、proc、agent、team） ----

def _ready(home):
    """讀之前：有 sqlite 帳本回 True；沒 boot 過回 False；還是舊的 state.json＝LedgerVersion。"""
    if exists(home):
        return True
    if legacy(home):
        raise LedgerError("LedgerVersion", "K 的帳本還是舊的 state.json（sqlite 之前的 kernel）；aos up（或 aos-kernel boot）換成 sqlite")
    return False


def read(home, default=None):
    """整份帳本（第 2 版同形的 dict，含反推的 on）；沒 boot 過回 default。"""
    if not exists(home):
        return default
    store = Store(home)
    try:
        return store.load()
    finally:
        store.close()


def write(home, state):
    """整份換掉（測試、匯入用）：沒有就建；帳本裡有而 state 沒有的鍵與列一律刪掉。"""
    store = Store(home, create=True)
    try:
        store.orig = _rows(store.conn)[1]
        store.save(dict(state))
    finally:
        store.close()


def proc(home, name):
    """查一筆行程（aos-kernel proc）：回 None（沒這個行程）或 {name, proc, cpu, discard}。沒 boot 過回 None。
    O(1)：只讀 procs 一列、busy 按 proc 查一列。"""
    if not _ready(home):
        return None
    conn = _connect(home)
    try:
        conn.execute("BEGIN")
        try:
            row = conn.execute("SELECT body FROM procs WHERE name=?", (name,)).fetchone()
            slot = conn.execute("SELECT cpu, body FROM busy WHERE proc=? ORDER BY ord LIMIT 1", (name,)).fetchone()
        finally:
            conn.execute("COMMIT")
    except sqlite3.Error as exc:
        raise LedgerError("ReadFailed", "帳本讀不到：%s（%s）" % (path_of(home), exc)) from exc
    finally:
        conn.close()
    if row is None:
        return None
    try:
        body = json.loads(slot[1]) if slot is not None else {}
        record = json.loads(row[0])
    except ValueError as exc:
        raise LedgerError("ReadFailed", "帳本裡 %s 那列讀不懂：%s" % (name, exc)) from exc
    return {"name": name, "proc": record, "cpu": slot[0] if slot is not None else None,
            "discard": bool(body.get("discard")) if isinstance(body, dict) else False}


def meta(home, *keys):
    """讀幾個 meta 鍵（{鍵: 值}，沒有的不在結果裡）；沒 boot 過回 {}。"""
    if not _ready(home):
        return {}
    conn = _connect(home)
    try:
        marks = ",".join("?" * len(keys))
        rows = conn.execute("SELECT key, value FROM meta WHERE key IN (%s)" % marks, keys).fetchall()
    except sqlite3.Error as exc:
        raise LedgerError("ReadFailed", "帳本讀不到：%s（%s）" % (path_of(home), exc)) from exc
    finally:
        conn.close()
    return {k: json.loads(v) for k, v in rows}


def knows(home, name):
    """kernel 還記得這張單嗎：帳本有這個行程、或出貨箱有這個檔名的回音（agent 的 already_posted 用）。"""
    if proc(home, name) is not None:
        return True
    replies = meta(home, "replies").get("replies") or []
    return any(isinstance(r, dict) and r.get("name") == name + ".json" for r in replies)


def procs(home):
    """{名: 行程紀錄}（continue --all 這種要掃全部的用）；沒 boot 過回 {}。"""
    if not _ready(home):
        return {}
    conn = _connect(home)
    try:
        return {n: json.loads(b) for n, b in conn.execute("SELECT name, body FROM procs ORDER BY rowid")}
    except sqlite3.Error as exc:
        raise LedgerError("ReadFailed", "帳本讀不到：%s（%s）" % (path_of(home), exc)) from exc
    finally:
        conn.close()



def peek_proc(home, name):
    """同 proc()，但讀不到（沒帳本、舊帳本、壞了）一律回 None、不丟例外（T2 郵差偷看用）。"""
    try:
        return proc(home, name)
    except (aos_home.HomeError, OSError, ValueError):
        return None


def peek_procs(home):
    """同 procs()，但讀不到一律回 {}、不丟例外（T2 郵差偷看用）。"""
    try:
        return procs(home)
    except (aos_home.HomeError, OSError, ValueError):
        return {}
