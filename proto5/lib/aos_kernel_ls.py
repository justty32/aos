"""aos-kernel ls（advice-r1，kernel/cli-ls.md）：先收成一份穩定的資料，再印成對齊的表或 JSON。

`ls_data()` 回的 dict 就是 `--json` 的 schema（_metainfo aos_kernel_ls 第 3 版：one-boot 拿掉 kernel cpu 與 kernel 池，
`kernel.cpu` 換成 `kernel.tick`；第 2 版是池式納入時以池取代逐顆 cpu）；文字版只從它排版，
兩邊看到的是同一份判定。第一行 health 的判定在 aos_kernel_health，這裡不改順序。
"""
import os
import time
import unicodedata

import aos_home
from aos_kernel_health import agent_marks, agents_health, health
from aos_kernel_info import DEFAULTS, KERNEL_POOL, KernelError, load_info

META = {"_type": "aos_kernel_ls", "_version": 3}  # one-boot（09-24）：kernel cpu 拿掉，kernel.cpu → kernel.tick、pools 不再有 kernel
NAME_WIDTH = 24   # 主表行程名最多幾格寬，超過截斷（-v 印全名）
QUEUE_SHOW = 8    # queue 行最多列幾個名字
SETTINGS = ("tick_ms", "interval_ms", "timeout_ms", "done_exit", "bad_after")  # v1 固定這五個


HINT_MAX = 1 << 20


def _read_small_json(path):
    """09-25 astra 必修 M4：kernel 判 bad 那格會叫 stderr_hint，不能被工作檔卡住。
    不阻塞地開、只讀普通檔、最多 1 MB；FIFO、裝置、太大的檔都當讀不到（呼叫者就指 target 本身）。"""
    import json
    import stat
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > HINT_MAX:
            raise ValueError("不是普通小檔")
        data = os.read(fd, HINT_MAX + 1)
    finally:
        os.close(fd)
    return json.loads(data.decode("utf-8"))


def stderr_hint(target):
    """bad 行程要人去看的檔：target 的 inst 有字面 stderr 就指它，否則指 target 本身。"""
    from pathlib import Path
    path = Path(target)
    try:
        raw = _read_small_json(path) if path.suffix == ".json" else None
    except (OSError, ValueError, UnicodeError):
        return str(path)
    value = raw.get("stderr") if isinstance(raw, dict) else None
    if isinstance(value, dict) and "$opt" in value:
        value = value.get("$val")
    if isinstance(value, str):
        return os.path.abspath(path.parent / value)
    return str(path)  # advice-r1（astra 必修 4）：沒有字面 stderr 就指 target 本身


def ls_data(home, snapshot, pool=None):
    """ls 的資料（--json 第 2 版）：池式（proto5-2 納入）以「一池一格」取代第 1 版的逐顆 cpu 與孩子表。

    pool：只看這池（procs 只留這池的，pools 只留這池並多一份 cpus 逐顆表）；池不在 info 也不在帳本＝NotFound。
    """
    from aos_kernel_rows import _Alive, cpu_rows, pool_rows
    home = os.path.abspath(home)
    info = load_info(home)
    code, message = health(home, snapshot=snapshot, info=info)
    marks = agent_marks(snapshot)
    if code == "ok":
        # fix-r5：kernel 正常時再看 agent 的暫停／重試，別印一個樂觀的 ok。
        code, message = agents_health(marks) or (code, message)
    ledger_pools = snapshot.get("pools") or {}
    if pool is not None and pool not in info["pools"] and pool not in ledger_pools:
        raise KernelError("NotFound", "沒有這個池：%s（info 與帳本都沒有）" % pool)
    daemon = snapshot["daemon"]
    alive = _Alive({daemon["home"]: bool(daemon["alive"])} if daemon.get("home") else {})
    summaries = {p: e.get("summary") for p, e in ledger_pools.items()}
    rows = pool_rows(home, info, snapshot, only=pool, summaries=summaries, alive=alive)
    if pool is not None:
        rows[pool]["cpus"] = cpu_rows(info, snapshot, pool, rows[pool])
    procs = []
    for name, proc in (snapshot.get("procs") or {}).items():
        mark = marks.get(name)
        proc = proc if isinstance(proc, dict) else {}
        if pool is not None and proc.get("pool") != pool:
            continue
        # astra 必修 2、3：帳本缺鍵或型別不對時正規化成 cli-ls.md 表上寫的型別，不原樣透傳。
        status = proc.get("status") if isinstance(proc.get("status"), str) else "unknown"
        target = proc.get("target") if isinstance(proc.get("target"), str) else None
        procs.append({
            "name": name, "once": bool(proc.get("once")), "pool": _text(proc.get("pool")),
            "status": status, "runs": _count(proc.get("runs")), "fails": _count(proc.get("fails")),
            "pending": bool(proc.get("pending")), "target": target,
            "mark": {"code": mark[0], "text": mark[1]} if mark else None,
            "parked": status == "queued" and proc.get("parked") is True,  # 09-24 停車
            "look": stderr_hint(target) if status == "bad" and target else None})
    # 帳本第 2 版沒有單一的 queue：排隊中的＝status queued 的行程（照帳本 procs 的順序）。
    queue = [p["name"] for p in procs if p["status"] == "queued"]
    by_status = {}
    for proc in procs:
        by_status[proc["status"]] = by_status.get(proc["status"], 0) + 1
    work = [r for p, r in rows.items() if p != KERNEL_POOL]
    reg = snapshot.get("ticker") if isinstance(snapshot.get("ticker"), dict) else None
    last = snapshot.get("last_tick_at")
    return {
        "_metainfo": dict(META),
        "health": {"code": code, "message": message},
        "kernel": {
            "home": home, "chain": snapshot["chain"], "phase": snapshot["phase"],
            "last_seq": snapshot["last_seq"],
            "daemon": {"home": os.path.abspath(daemon["home"]) if daemon.get("home") else None,
                       "alive": bool(daemon["alive"])},
            "tick": {"registered": reg is not None,
                     "every_ms": reg.get("every_ms") if reg else None,
                     "fails": reg.get("fails", 0) if reg else None,
                     "last_exit": reg.get("last_exit") if reg else None,
                     "last_at": last if isinstance(last, (int, float)) else None},
            "settings": {key: info.get(key, DEFAULTS[key]) for key in SETTINGS}},
        "pools": rows, "procs": procs, "queue": queue,
        "counts": {"pools": {"total": len(work), "want": sum(r["want"] for r in work),
                             "sent": sum(r["sent"] or 0 for r in work), "busy": sum(r["busy"] or 0 for r in work),
                             "idle": sum(r["idle"] or 0 for r in work),
                             "draining": sum(r["draining"] or 0 for r in work)},
                   "procs": {"total": len(procs), "repeat": sum(not p["once"] for p in procs),
                             "once": sum(p["once"] for p in procs), "status": by_status,
                             "parked": sum(p["parked"] for p in procs)},
                   "queue": len(queue)}}


def _text(value):
    return value if isinstance(value, str) else None


def _count(value):
    return value if type(value) is int else 0


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _cut(text, limit):
    """太長就砍中間：頭留辨識用的前綴、尾留區分用的流水號（-v 印全名）。"""
    if _width(text) <= limit:
        return text
    head, tail = "", ""
    for ch in text:
        if _width(head + ch) > (limit - 1) * 2 // 3:
            break
        head += ch
    for ch in reversed(text):
        if _width(head + ch + tail) > limit - 1:
            break
        tail = ch + tail
    return head + "…" + tail


def _table(header, rows, right=()):
    widths = [max(_width(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    lines = []
    for row in [header, *rows]:
        cells = []
        for i, cell in enumerate(row):
            pad = " " * (widths[i] - _width(str(cell)))
            cells.append(pad + str(cell) if i in right else str(cell) + pad)
        lines.append(("  " + "  ".join(cells)).rstrip())
    return lines


def render(data, verbose=False, procs=False):
    from aos_kernel_rows import cpu_line, pool_lines
    k, counts = data["kernel"], data["counts"]
    phase = k["phase"] or "沒 boot 過"
    if k["phase"] in ("running", "stopping") and not k["daemon"]["alive"]:
        # 試玩 one-boot 卡點 3：帳本寫 running，但 daemon 不在就沒人開 tick，別讓人以為還在跑。
        phase = "%s（帳本這樣寫；daemon 不在，其實沒在跑）" % k["phase"]
    lines = ["health " + data["health"]["message"],
             "kernel  %s  seq %s  daemon %s  tick %sms" % (
                 phase, "-" if k["last_seq"] is None else k["last_seq"],
                 "alive" if k["daemon"]["alive"] else "dead", k["settings"]["tick_ms"])]
    tick = k["tick"]
    if not k["daemon"]["alive"]:
        text = "  tick 沒人開（daemon 沒在跑；aos up）"
    elif tick["registered"]:
        ago = "-" if tick["last_at"] is None else "%d 秒前" % max(0, time.time() - tick["last_at"])
        text = "  tick 由 daemon 開：上一格 %s%s" % (ago, "、連敗 %d" % tick["fails"] if tick["fails"] else "")
    if k["daemon"]["alive"] and not tick["registered"]:
        text = "  tick 沒人開（daemon 沒登記這個 kernel；aos up）"
    if verbose:
        lines += ["  K       " + k["home"], "  D       " + (k["daemon"]["home"] or "-"),
                  "  chain   " + (k["chain"] or "-")]
    lines.append(text)
    c = counts["pools"]
    lines.append("pool    %d 個工作池：要 %d 顆、忙 %d、閒 %d%s" % (
        c["total"], c["want"], c["busy"], c["idle"], "、收掉中 %d" % c["draining"] if c["draining"] else ""))
    rows = data["pools"]
    # daemon 欄：跟 kernel 池同一個 daemon 家的只印 dpool，別的家印全路徑（同 cpu ls）。
    lines += ["  " + line for line in pool_lines(k["home"], {"daemon": k["daemon"]["home"]}, rows)]
    for row in rows.values():
        for item in row.get("cpus") or []:
            lines.append("    " + cpu_line(item))
    p = counts["procs"]
    head = "proc    %d 個" % p["total"]
    if p["total"]:
        head += "（反覆 %d、once %d）：%s" % (p["repeat"], p["once"], "、".join(
            "%s %d" % (status, n) for status, n in sorted(p["status"].items(), key=lambda kv: str(kv[0]))))
    if p["parked"]:
        head += "；停車 %d" % p["parked"]  # 09-24 停車：退 102 在等回音／輸入的
    lines.append(head)
    # 池式（proto5-2 納入）：上萬個行程時不逐個印；預設只列有事的（bad、暫停／重試中），--procs 才全列。
    shown = [proc for proc in data["procs"] if procs or proc["status"] == "bad" or proc["mark"]]
    table = [[proc["name"] if verbose else _cut(proc["name"], NAME_WIDTH), "once" if proc["once"] else "反覆",
              proc["status"] or "-", proc["runs"], proc["fails"], "等" if proc["pending"] else "-",
              proc["mark"]["text"] if proc["mark"] else ""] for proc in shown]
    if table:
        lines += _table(["行程", "種類", "狀態", "runs", "fails", "回音", "備註"], table, right=(3, 4))
    if len(shown) < p["total"]:
        lines.append("  （其餘 %d 個沒事的沒列；--procs 全列）" % (p["total"] - len(shown)))
    for proc in shown:
        if proc["look"]:
            lines.append("  %s 壞了，看 %s" % (proc["name"], proc["look"]))
        if verbose and proc["target"]:
            lines.append("  %s  target %s" % (proc["name"], proc["target"]))
    queue = data["queue"]
    names = queue if verbose else [_cut(n, NAME_WIDTH) for n in queue[:QUEUE_SHOW]]
    more = "" if verbose or len(queue) <= QUEUE_SHOW else " …還有 %d 個" % (len(queue) - QUEUE_SHOW)
    lines.append("queue   " + ("%d：%s%s" % (len(queue), " ".join(names), more) if queue else "-"))
    return "\n".join(lines)
