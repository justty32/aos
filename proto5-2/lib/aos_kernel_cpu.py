"""kernel 的 `cpu add／rm／ls` 與按池摘要（kernel-cli.md 的 cpu 三段、ls 的池行）。

cpu add／rm 只改 `K/info.json` 的池表：拿 `K/.info.lock` 獨占鎖（等 10 秒）→ 讀 → 改 → 驗 → 唯一 .tmp → rename。
不放任何單、不用 boot；kernel 在跑的話下一格就照新數字做（kernel-pools）。
cpu ls 讀帳本＋daemon 的 summary.json（O(池數)）；`--pool P` 再逐顆讀 kids 檔（O(池大小)）。
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import time

import aos_daemon
import aos_home
from aos_kernel_info import (
    KERNEL_POOL, CLIUsage, KernelError, _parse_info, load_info, member_set, members, pool_location,
    pool_name_ok, split_key,
)

LOCK_WAIT_S = 10.0


class UsageError(CLIUsage):
    """用法錯（退 2），但代號不是 Usage（例：PoolExists）。"""
    def __init__(self, code, msg):
        KernelError.__init__(self, code, msg)


# ---- 寫 info（kernel-cli「cpu add／rm 怎麼寫 info」） ----

def _lock(home, wait_s=None):
    wait_s = LOCK_WAIT_S if wait_s is None else wait_s
    fd = os.open(home / ".info.lock", os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(fd)
                raise KernelError("Busy", "別的 aos-kernel cpu add／rm 正拿著 %s，等了 %d 秒；等一下再試" % (
                    home / ".info.lock", wait_s))
            time.sleep(.02)


def _literal_dict(value):
    return isinstance(value, dict) and not any(isinstance(k, str) and k.startswith("$") for k in value)


def _edit(home, change):
    """鎖著做完 讀→改→驗→寫；change(raw, info) 只改 raw 的 pools.P.count／skip／新池那格，回要印的字。"""
    home = Path(home).absolute()
    aos_home.read_json(home / "info.json")  # 家不在就先報讀不到，不在別人的地方建鎖檔
    fd = _lock(home)
    try:
        raw = aos_home.read_json(home / "info.json")
        info = _parse_info(home, copy.deepcopy(raw))
        if not _literal_dict(raw) or not _literal_dict(raw.get("pools")):
            raise KernelError("NotLiteral", "info.json 的 pools 用了指示詞，cpu add／rm 不改；請直接編 %s" % (home / "info.json"))
        message = change(raw, info)
        _parse_info(home, copy.deepcopy(raw))  # 改完一樣要過讀驗；過不了就不寫
        aos_home.write_json(home / "info.json", raw)
        return message
    finally:
        os.close(fd)


def _literal_pool(raw, pool):
    """既有池那格要是字面物件、count／skip 是字面值，CLI 才改；否則請人手改（D-37）。"""
    config = raw["pools"][pool]
    ok = (_literal_dict(config) and type(config.get("count")) is int and
          ("skip" not in config or (isinstance(config["skip"], list) and all(type(s) is int for s in config["skip"]))))
    if not ok:
        raise KernelError("NotLiteral", "池 %s 的 count／skip 用了指示詞，cpu add／rm 不改；請直接編 info.json" % pool)
    return config


def _set_count(config, count, skip):
    """寫回 count 與整理過的 skip：只排序、去重，一律保留、不丟（D-38，隊長裁定見 decisions.md：
    Q4 永久退休優先於 skip 長度，代價是 skip 只增不減，要清得手改 info）。"""
    skip = sorted(set(skip))
    config["count"] = count
    if skip or "skip" in config:
        config["skip"] = skip


def kernel_running(home):
    """kernel 現在會不會照新數字做：帳本 phase running、kernel 池的 daemon 活著、它那邊的 kernel 池有一顆在跑。"""
    try:
        state = aos_home.read_state(home, {})
        entry = (state.get("pools") or {}).get(KERNEL_POOL)
        if state.get("phase") != "running" or not state.get("chain") or not entry:
            return False
        if not aos_daemon.is_alive(entry["daemon"]):
            return False
        summary = aos_daemon.pool_summary(entry["daemon"], entry["dpool"])
        return bool(summary) and summary.get("running", 0) > 0
    except (aos_home.HomeError, OSError, KeyError, TypeError, AttributeError):
        return False


def _check_pool_arg(pool):
    if not pool_name_ok(pool):
        raise CLIUsage("池名不合法（1～64 字、只用 A-Z a-z 0-9 _ . -）：%r" % pool)
    if pool == KERNEL_POOL:
        raise CLIUsage("kernel 池永遠 1 顆，不能 cpu add／rm")


def _parse_envs(values):
    envs = {}
    for item in values or ():
        key, sep, value = item.partition("=")
        if not sep or not key or key.startswith("$") or "\0" in item:
            raise CLIUsage("--env 要寫成 KEY=VALUE（KEY 不能空、不能用 $ 開頭）：%r" % item)
        if key in envs:
            raise CLIUsage("--env %s 給了兩次" % key)
        envs[key] = value
    return envs


def _report(home, pool, before, after):
    lines = ["pool %s count %d -> %d" % (pool, before, after)]
    if not kernel_running(home):
        lines.append("kernel 沒在跑：下次 boot 生效（aos-kernel boot --target %s）" % home)
    return "\n".join(lines)


def cpu_add(home, pool, count=None, env=None, daemon=None, dpool=None):
    home = Path(home).absolute()
    _check_pool_arg(pool)
    count = 1 if count is None else count
    if type(count) is not int or count < 0:
        raise CLIUsage("--count 必須是非負整數")
    envs = _parse_envs(env)
    if daemon == "" or dpool == "":
        raise CLIUsage("--daemon／--dpool 不可為空")
    if dpool is not None and not pool_name_ok(dpool):
        raise CLIUsage("--dpool 不合法（同池名規則）：%r" % dpool)

    def change(raw, info):
        pools = raw["pools"]
        if pool in pools:
            if env or daemon is not None or dpool is not None:
                raise UsageError("PoolExists", "池 %s 已經在了：cpu add 只加 count；改既有池的 envs／daemon／dpool 請直接編 %s"
                                 "（影響見 kernel-info §4）" % (pool, home / "info.json"))
            config = _literal_pool(raw, pool)
            before = config["count"]
            _set_count(config, before + count, config.get("skip", []))
            return _report(home, pool, before, before + count)
        config = {"count": count}
        if envs:
            config["envs"] = envs
        if daemon is not None:
            config["daemon"] = os.path.abspath(os.path.expanduser(daemon))
        if dpool is not None:
            config["dpool"] = dpool
        pools[pool] = config
        return _report(home, pool, 0, count)
    return _edit(home, change)


def cpu_rm(home, name=None, pool=None, count=None):
    home = Path(home).absolute()
    if (name is None) == (pool is None):
        raise CLIUsage("cpu rm 要給 P/<i>，或 --pool P --count N（二選一）")
    if name is not None:
        if count is not None:
            raise CLIUsage("cpu rm P/<i> 不能再給 --count")
        parsed = split_key(name)
        if parsed is None:
            raise CLIUsage("cpu 全名要寫成 P/<i>（i 是不帶前導 0 的十進位）：%r" % name)
        pool, number = parsed
    else:
        if count is None:
            raise CLIUsage("cpu rm --pool P 要給 --count N")
        if type(count) is not int or count <= 0:
            raise CLIUsage("--count 必須是正整數")
        number = None
    _check_pool_arg(pool)

    def change(raw, info):
        if pool not in raw["pools"]:
            raise KernelError("NotFound", "沒有這個池：%s（看 aos-kernel cpu ls --target %s）" % (pool, home))
        config = _literal_pool(raw, pool)
        before, skip = config["count"], list(config.get("skip", []))
        if number is not None:
            if number not in set(members(before, skip)):
                raise KernelError("NotFound", "%s/%d 不是池 %s 現在的成員（看 aos-kernel cpu ls --target %s --pool %s）" % (
                    pool, number, pool, home, pool))
            _set_count(config, before - 1, skip + [number])
            return _report(home, pool, before, before - 1)
        if count > before:
            raise CLIUsage("池 %s 只有 %d 顆，不能收 %d 顆" % (pool, before, count))
        _set_count(config, before - count, skip)
        return _report(home, pool, before, before - count)
    return _edit(home, change)


# ---- 按池摘要（cpu ls、ls 共用） ----

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
    names = list(dict.fromkeys([KERNEL_POOL, *info["pools"], *(state.get("pools") or {})]))
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
           "new_location": list(loc) if loc else None}
    if entry is None:
        row.update(sent=None, busy=0, idle=None, draining=None, pending=None, error=None, waiting=[])
    elif pool == KERNEL_POOL:
        row.update(sent=entry["sent"]["count"], busy=None, idle=None, draining=None,
                   pending=entry.get("pending"), error=entry.get("error"), waiting=[])
    else:
        row.update(sent=entry["sent"]["count"], busy=len(busy), idle=len(entry.get("free") or []),
                   draining=entry.get("draining", 0), pending=entry.get("pending"), error=entry.get("error"),
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
        part = " ".join("%s %s" % (k, summary.get(k, 0)) for k in ("running", "restarting", "pending", "dead", "failed"))
        for k in ("killing", "draining"):
            if summary.get(k):
                part += " %s %s" % (k, summary[k])
    tails = []
    if not row["declared"]:
        tails.append("還沒宣告（kernel 在跑就下一格送，否則下次 boot）")
    if row["pending"]:
        tails.append("scale 單在路上" + ("，daemon 沒在跑" if not row["daemon_alive"] else "（等回音）"))
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


def cpu_line(item):
    status = item["status"] + (" " + str(item["proc"]) if item["proc"] is not None else "")
    kid = item["daemon"]
    if kid is not None:
        daemon = "daemon %s gen %s" % (kid.get("state"), _num(kid.get("gen")))
    else:
        daemon = "daemon pending" if item["declared"] else "daemon -"
    return "%s  %s  %s" % (item["cpu"], status, daemon)


def pool_lines(home, info, rows):
    width = max((len(p) for p in rows), default=0)
    return [row_line(home, info, row, width) for row in rows.values()]


def cpu_ls(home, pool=None, as_json=False):
    home = Path(home).absolute()
    info = load_info(home)
    state = aos_home.read_state(home, {})
    rows = pool_rows(home, info, state, only=pool)
    if pool is not None and not rows:
        raise KernelError("NotFound", "沒有這個池：%s（info 與帳本都沒有）" % pool)
    if pool is not None:
        rows[pool]["cpus"] = cpu_rows(info, state, pool, rows[pool])
    if as_json:
        return json.dumps({"pools": rows}, ensure_ascii=False)
    lines = pool_lines(home, info, rows)
    if pool is not None:
        lines.extend(cpu_line(item) for item in rows[pool]["cpus"])
    return "\n".join(lines)
