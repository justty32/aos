"""按池摘要（每池一格／一池一行）與一顆一行：`aos-kernel cpu ls` 與 `aos-kernel ls`（aos_kernel_ls）共用。

只讀：帳本、info 池表、daemon 的 summary.json（O(池數)）；`cpu_rows()` 才逐顆讀 kids 檔（O(池大小)）。
字眼約定見 kernel-cli.md 的 cpu ls；`--json` 讀的是 `pool_rows()`／`cpu_rows()` 回的 dict，印的字另外換。
"""
import aos_daemon
import aos_home
from aos_kernel_info import KERNEL_POOL, member_set, members, pool_location, split_key


class _Alive:
    def __init__(self, known=None):
        self.cache = dict(known or {})

    def __call__(self, daemon):
        if daemon not in self.cache:
            try:
                self.cache[daemon] = bool(daemon) and aos_daemon.is_alive(daemon)
            except OSError:
                self.cache[daemon] = False
        return self.cache[daemon]


def _summary(daemon, dpool):
    if not daemon:
        return None
    try:
        return aos_daemon.pool_summary(daemon, dpool)
    except (aos_home.HomeError, OSError, AttributeError):
        return None


def pool_rows(home, info, state, only=None, summaries=None, alive=None):
    """每池一格 dict（info 的池＋帳本裡還在的池）；summaries 可給 {池: summary} 省得重讀。"""
    alive = alive or _Alive()
    # one-boot：沒有 kernel 池了（舊 info／帳本留下的 kernel 這格略過）。
    names = [p for p in dict.fromkeys([*info["pools"], *(state.get("pools") or {})]) if p != KERNEL_POOL]
    rows = {}
    for pool in names:
        if only is not None and pool != only:
            continue
        rows[pool] = pool_row(home, info, state, pool, summaries, alive)
    return rows


def pool_row(home, info, state, pool, summaries=None, alive=None):
    alive = alive or _Alive()
    config = info["pools"].get(pool)
    entry = (state.get("pools") or {}).get(pool)
    loc = pool_location(info, pool)
    daemon, dpool = (entry["daemon"], entry["dpool"]) if entry else (loc if loc else (None, pool))
    if summaries is not None and pool in summaries:
        summary = summaries[pool]
    else:
        summary = _summary(daemon, dpool)
    want = config["count"] if config else 0
    w = set(members(config["count"], config["skip"])) if config else set()
    prefix = pool + "/"
    busy = {k: v for k, v in (state.get("busy") or {}).items() if k.startswith(prefix)}
    waiting = [v.get("proc") for k, v in busy.items() if split_key(k) and split_key(k)[1] not in w]
    row = {"pool": pool, "want": want, "daemon": daemon, "dpool": dpool,
           "daemon_alive": alive(daemon) if daemon else False, "summary": summary,
           "declared": entry is not None, "removing": config is None,
           "moving": bool(entry) and loc is not None and (entry["daemon"], entry["dpool"]) != tuple(loc),
           "new_location": list(loc) if loc else None, "phase": state.get("phase")}
    if entry is None:
        row.update(sent=None, busy=0, idle=None, draining=None, pending=None, error=None, waiting=[])
    elif pool == KERNEL_POOL:
        row.update(sent=entry["sent"]["count"], busy=None, idle=None, draining=None,
                   pending=entry.get("pending"), error=entry.get("error"), waiting=[])
    else:
        # draining 即時算「不在 W 且在 busy」（run.md 碰到的問題 3）：帳本自己的 draining 計數要等一格
        # 才重算，`cpu rm` 剛下時會跟單顆行的 draining 狀態對不上；這裡不碰帳本，只在顯示時多算一次。
        row.update(sent=entry["sent"]["count"], busy=len(busy), idle=len(entry.get("free") or []),
                   draining=len(waiting), pending=entry.get("pending"), error=entry.get("error"),
                   waiting=waiting)
    row["gone"] = pool_gone(row)
    return row


def pool_gone(row):
    """摘要檔不在，但 kernel 以為 daemon 那邊有成員（sent 不空、也不是正在縮到 0）。"""
    if row["summary"] is not None or not row["sent"]:
        return False
    pending = row.get("pending")
    return not (pending and pending.get("count") == 0)


def _daemon_label(info, row):
    if row["daemon"] is None:
        return "daemon ?"
    if row["daemon"] == info.get("daemon"):
        return "daemon %s" % row["dpool"]
    return "daemon %s %s" % (row["daemon"], row["dpool"])


def _num(value):
    return "-" if value is None else str(value)


def row_line(home, info, row, width=0):
    """cpu ls 的一池一行（ls 的池摘要同格式）。"""
    head = "%-*s  want %s  sent %s" % (width, row["pool"], row["want"], _num(row["sent"]))
    if row["pool"] != KERNEL_POOL and row["declared"]:
        head += "  busy %s  idle %s  draining %s" % (row["busy"], row["idle"], row["draining"])
    label = _daemon_label(info, row)
    summary = row["summary"]
    if row["daemon"] is None:
        part = "解不出 daemon 家（在 info.json 寫 daemon；boot 會報 NoDaemon）"
    elif row["error"]:
        part = "錯誤 %s（%s）" % (row["error"].get("code"), row["error"].get("message") or "-")
    elif row["gone"]:
        part = "池不見了（跑 aos-kernel boot --target %s）" % home
    elif summary is None:
        part = "沒有這池"
    else:
        # restarting 是 running 的子集，寫進 running 那格（使用者代裁，09-24）；--json 照舊兩欄分開。
        restarting = summary.get("restarting", 0)
        part = "running %s%s " % (summary.get("running", 0), "（含 restarting %s）" % restarting if restarting else "")
        part += " ".join("%s %s" % (k, summary.get(k, 0)) for k in ("pending", "dead", "failed"))
        for k in ("killing", "draining"):
            if summary.get(k):
                part += " %s %s" % (k, summary[k])
    tails = []
    if not row["declared"]:
        tails.append("還沒宣告（kernel 在跑就下一格送，否則下次 boot）")
    if row["pending"]:
        if row.get("phase") == "stopped":
            # run.md 碰到的問題 4：kernel 已停機，這張回音本來就留給下次 boot 讀，「在路上」會讓人以為卡住。
            tails.append("停機中，下次 boot 收回音")
        elif not row["daemon_alive"]:
            tails.append("宣告已送出，daemon 沒在跑（daemon 一上線就會收到）")
        else:
            # run.md 碰到的問題 1：daemon 早就拉齊了、只是帳本還沒收回音，等一格就好，不是卡住。
            tails.append("宣告已送出，下一格確認")
    elif row["daemon"] is not None and not row["daemon_alive"]:
        tails.append("daemon 沒在跑")
    if row["moving"]:
        tails.append("搬池中（舊位置收完才換到 %s %s）" % tuple(row["new_location"]))
    if row["removing"] and row["pool"] != KERNEL_POOL:
        tails.append("移除中（info 已拿掉，縮到 0 收完就忘掉）")
    if row["waiting"]:
        tails.append("收掉中 %d 顆，等 %s" % (len(row["waiting"]), "、".join(map(str, row["waiting"]))))
    line = "%s   %s: %s" % (head, label, part)
    return line + "".join("   " + t for t in tails)


def cpu_rows(info, state, pool, row):
    """--pool P：一顆一行（O(池大小)），kids 檔逐顆讀。"""
    config = info["pools"].get(pool)
    entry = (state.get("pools") or {}).get(pool) or {}
    w = set(members(config["count"], config["skip"])) if config else set()
    s = member_set(entry.get("sent"))
    pend = member_set(entry.get("pending")) if entry.get("pending") else set()
    prefix = pool + "/"
    busy = {}
    for key, slot in (state.get("busy") or {}).items():
        parsed = split_key(key) if key.startswith(prefix) else None
        if parsed:
            busy[parsed[1]] = slot.get("proc")
    out = []
    for i in sorted(w | s | pend | set(busy)):
        if pool == KERNEL_POOL:
            status, proc = "-", None
        elif i in busy:
            status, proc = ("busy" if i in w else "draining"), busy[i]
        elif i in w and i in s:
            status, proc = "idle", None
        elif i in w:
            status, proc = "待宣告", None
        else:
            status, proc = "收掉中", None
        kid = None
        if row["daemon"]:
            try:
                kid = aos_daemon.pool_kid(row["daemon"], row["dpool"], i)
            except (aos_home.HomeError, OSError, AttributeError):
                kid = None
        out.append({"cpu": "%s/%d" % (pool, i), "status": status, "proc": proc,
                    "daemon": None if kid is None else {"state": kid.get("state"), "gen": kid.get("gen"),
                                                         "pid": kid.get("pid")},
                    "declared": i in s})
    return out


# run.md 碰到的問題 1／3：只換 cpu ls --pool 印出來的字眼，`cpu_rows()` 回的 status（含 --json）不動，
# 免得改到協定（kernel-cli.md §「cpu ls」）約定的欄位值。
_STATUS_LABEL = {"待宣告": "等 daemon 確認"}


def cpu_line(item):
    status = _STATUS_LABEL.get(item["status"], item["status"]) + (
        " " + str(item["proc"]) if item["proc"] is not None else "")
    kid = item["daemon"]
    if kid is not None:
        daemon = "daemon %s gen %s" % (kid.get("state"), _num(kid.get("gen")))
    elif item["declared"] and item["status"] == "收掉中":
        # 剛收掉那一刻 kids 檔可能還沒消失／還沒被讀到；「daemon pending」讀起來像要再拉一顆。
        daemon = "daemon 在收"
    else:
        daemon = "daemon pending" if item["declared"] else "daemon -"
    return "%s  %s  %s" % (item["cpu"], status, daemon)


def pool_lines(home, info, rows):
    width = max((len(p) for p in rows), default=0)
    return [row_line(home, info, row, width) for row in rows.values()]
