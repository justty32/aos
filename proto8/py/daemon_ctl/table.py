"""daemon_ctl 名單：尋找 daemon、讀取狀態表並解析子項與上一層狀態。"""
import json
import os
import time

from .base import Fail, NAMES, PATHS, STATE



def find_daemon(flag=None):
    """--daemon ＞ $AOS_DAEMON ＞ cwd 的 ./.stack（11-05 題 3）；轉絕對。"""
    d = flag or os.environ.get("AOS_DAEMON", "")
    if not d and os.path.isdir(".stack"):
        d = ".stack"
    if not d:
        raise Fail("DaemonMissing", "no --daemon, AOS_DAEMON not set, and no .stack folder in the cwd (point it at the daemon's $AOS_STACK folder)")
    if not os.path.isdir(d):
        raise Fail("DaemonMissing", "daemon folder not found: %s" % d)
    return os.path.realpath(d)   # 11-05 B 線：daemon 的表相對它 stack 的真實路徑（解開捷徑）算，這裡也解開才拼得回



def names_of(d):
    """讀取 daemon 回報的檔名；壞值用預設，信箱 null 保留。"""
    try:
        with open(os.path.join(d, STATE), encoding="utf-8") as fh:
            st = json.load(fh)
    except (OSError, ValueError):
        st = {}
    out = dict(NAMES)
    if isinstance(st, dict):
        for key in NAMES:
            value = st.get(key)
            if isinstance(value, str) and value:
                out[key] = value
            elif key == "procs_ctl_mailbox" and key in st and value is None:
                out[key] = None
    return out



def table(d, v):
    """procs_state 的表：物件原樣；切檔（{"$ref": [分檔, …]}）照順序讀回來合起來。"""
    if isinstance(v, dict) and isinstance(v.get("$ref"), list):
        out = {}
        for ref in v["$ref"]:
            with open(os.path.join(d, ref), encoding="utf-8") as fh:
                out.update(json.load(fh))
        return out
    if not isinstance(v, dict):
        raise ValueError("the table is not an object")
    return v


def resolve(d, row):
    """表上一列的 stack／ws／exec／def 拼回絕對（11-05：daemon 存相對 daemon stack）。exec 的 # 片段照留；
    值照字面（D 已 realpath）。不是字串的（null、內嵌單子）不動。回新的一列。"""
    out = dict(row)
    for k in PATHS:
        v = out.get(k)
        if isinstance(v, str) and v:
            f, h, p = v.partition("#")
            out[k] = (os.path.normpath(os.path.join(d, f)) if f else f) + h + p
    return out



def state(d):
    """讀名單窗與切檔；解析失敗時稍等一次，避免讀到寫入交界。"""
    path = os.path.join(d, STATE)
    if not os.path.isfile(path):
        raise Fail("StateMissing", "%s not found (daemon not started yet, or procs_state is off)" % path)
    for attempt in range(2):
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            procs = table(d, st.get("procs", {}))
            return {"daemon": st.get("daemon"), "responded_at": st.get("responded_at"),
                    "mailbox_warning": st.get("mailbox_warning"),
                    "procs": {n: resolve(d, r) if isinstance(r, dict) else r for n, r in procs.items()}}
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            if attempt:
                raise Fail("StateBad", "cannot parse %s: %s" % (path, exc))
            time.sleep(0.05)


def rows(d):
    return state(d)["procs"]



def row_of(d, name):
    """表上那一列；表上沒有＝ProcMissing（不看小格資料夾在不在）。"""
    r = rows(d).get(name)
    if not isinstance(r, dict):
        raise Fail("ProcMissing", "%s is not on the daemon table (only running, stuck, stopping, stopped, sleeping rows count; removed ones are gone, see aos-daemon-ctl ls)" % name)
    return r


def cell_of(d, name, row=None):
    """proc 的 stack：procs_state 那一列的 stack（11-03 procs § 2b；預設小格 <D>/procs/<名字> 也是 daemon 寫在列上的）。拿 stack 只在這裡。"""
    r = row_of(d, name) if row is None else row
    s = r.get("stack")
    if not isinstance(s, str) or not s:
        raise Fail("StateBad", "the row of %s has no stack" % name)
    return s.rstrip("/") or "/"


def supervisor(d, st):
    """只讀上一層對這台 daemon 的看法，不自行判活。"""
    up = st.get("daemon")
    if up is None:
        return None, None, None
    if not isinstance(up, str) or not os.path.isabs(up):
        return up, None, "relative path as the daemon inherited it; cannot tell where it is"
    try:
        procs = rows(up)
    except Fail as exc:
        if exc.code not in ("StateMissing", "StateBad"):
            raise
        return up, None, "no readable procs_state.json there"
    for row in procs.values():
        stack = row.get("stack") if isinstance(row, dict) else None
        if isinstance(stack, str) and os.path.realpath(stack) == os.path.realpath(d):
            return up, row.get("phase"), row.get("reason")
    return up, None, "this daemon is not on its table"
