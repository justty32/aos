"""daemon_ctl 名單：尋找 daemon、解析狀態表、自檢子項與篩選已有 stack 的久未修改列。"""
import datetime
import json
import os
import re
import stat
import time

import aos_flags
import daemon_ctl as _pkg

from .base import Fail, NAMES, PATHS, STATE, STATE_FLUX
from .entry import read_loop
from .state_path import TableFile, names_at, state_at



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
    """讀取 daemon 回報的檔名；壞值用預設，信箱 null 保留。d 是表檔（TableFile，查詢信問來的）＝讀那份檔。"""
    if isinstance(d, TableFile):
        return names_at(d)
    st = aos_flags.read_window(_pkg.PROG, os.path.join(d, STATE))
    out = dict(NAMES)
    if isinstance(st, dict):
        for key in NAMES:
            value = st.get(key)
            if isinstance(value, str) and value:
                out[key] = value
            elif key == "procs_requests" and key in st and value is None:
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



def mailbox_warning(d):
    """獨立讀 daemon 的 state_flux；設定讀不到用預設名，關窗或讀不到回音就沒有警告。"""
    try:
        name = read_loop(os.path.join(d, "daemon.json")).get("state_flux", STATE_FLUX)
    except Fail:
        name = STATE_FLUX
    if not isinstance(name, str) or not name:
        return None
    st = aos_flags.read_window(_pkg.PROG, os.path.join(d, name))
    return st.get("mailbox_warning") if st is not None else None


def state(d):
    """讀名單窗與切檔，警告獨立讀 state_flux；名單解析失敗時稍等一次。
    d 是表檔（TableFile，查詢信問來的）＝讀那份檔，相對路徑從它所在的資料夾算（state_at）；rows、row_of、cell_of 等跟著吃表檔。"""
    if isinstance(d, TableFile):
        return state_at(d)
    path = os.path.join(d, STATE)
    if not os.path.isfile(path):
        raise Fail("StateMissing", "%s not found (daemon not started yet, or procs_state is off)" % path)
    for attempt in range(2):
        try:
            with open(path, encoding="utf-8") as fh:
                st = json.load(fh)
            procs = table(d, st.get("procs", {}))
            return {"daemon": st.get("daemon"),
                    "mailbox_warning": mailbox_warning(d),
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


def duration(value):
    """prune 的門檻只收正整數加 s／m／h／d，不設隱含清空值。"""
    match = re.fullmatch(r"([0-9]+)([smhd])", value)
    try:
        number = int(match[1]) if match else 0
    except ValueError:
        number = 0
    if number <= 0:
        raise Fail("ArgumentsBad", "--older-than needs a positive integer followed by s, m, h or d (for example 7d)")
    return number * {"s": 1, "m": 60, "h": 3600, "d": 86400}[match[2]]


def inspect_row(d, name, row):
    """檢查 stack、公開 ctl 與 reason；待起列不要求 stack，不讀子項私有語意。"""
    from .ctl import need_ctl

    stack, ctl = need_ctl(d, name, row)
    problems = []
    pending = (row.get("phase") in {"stopped", "sleeping"} and
               row.get("pid") is None and row.get("code") is None)
    if not os.path.isdir(stack) and not pending:
        problems.append("stack missing")
    try:
        with open(ctl, encoding="utf-8") as fh:
            value = json.load(fh)
        if not isinstance(value, dict):
            problems.append("ctl is not a JSON object: %s" % ctl)
    except FileNotFoundError:
        pass  # ctl 尚未寫過不算問題。
    except ValueError:
        problems.append("ctl is not a JSON object: %s" % ctl)
    except OSError as exc:
        problems.append("cannot read ctl %s: %s" % (ctl, exc))
    if row.get("phase") == "stopped" and row.get("reason") is not None:
        problems.append(str(row["reason"]))
    return "; ".join(problems)


def last_change(stack):
    """stack 本身及直接底下檔案的最新 mtime；不進子目錄，缺 stack 回 None。"""
    try:
        info = os.stat(stack)
        if not stat.S_ISDIR(info.st_mode):
            return None
        latest = info.st_mtime
        with os.scandir(stack) as entries:
            for entry in entries:
                try:
                    if entry.is_file():
                        latest = max(latest, entry.stat().st_mtime)
                except FileNotFoundError:
                    continue  # 巡查途中被移走的檔案已不在直接底下。
        return latest
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Fail("StateBad", "cannot inspect stack %s: %s" % (stack, exc))


def prune_candidates(d, procs, seconds, now):
    """只選 stack 存在、stopped／sleeping 且最新修改嚴格早於門檻的列；不修改表或檔案。"""
    for name, row in procs.items():
        if row.get("phase") not in {"stopped", "sleeping"}:
            continue
        changed = last_change(cell_of(d, name, row))
        if changed is None:
            continue
        if now - changed > seconds:
            try:
                stamp = datetime.datetime.fromtimestamp(changed, datetime.timezone.utc).isoformat()
            except (OverflowError, OSError, ValueError) as exc:
                raise Fail("StateBad", "cannot format last change for %s: %s" % (name, exc))
            yield name, stamp
