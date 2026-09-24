"""aos-kernel ls（advice-r1，kernel/cli-ls.md）：先收成一份穩定的資料，再印成對齊的表或 JSON。

`ls_data()` 回的 dict 就是 `--json` 的 schema（_metainfo aos_kernel_ls 第 1 版）；文字版只從它排版，
兩邊看到的是同一份判定。第一行 health 的判定在 aos_kernel_health，這裡不改順序。
"""
import os
import unicodedata

import aos_daemon
import aos_home
from aos_kernel_health import agent_marks, agents_health, health
from aos_kernel_info import DEFAULTS, load_info

META = {"_type": "aos_kernel_ls", "_version": 1}
NAME_WIDTH = 24   # 主表行程名最多幾格寬，超過截斷（-v 印全名）
QUEUE_SHOW = 8    # queue 行最多列幾個名字
SETTINGS = ("tick_ms", "interval_ms", "timeout_ms", "done_exit", "bad_after")  # v1 固定這五個


def stderr_hint(target):
    """bad 行程要人去看的檔：target 的 inst 有字面 stderr 就指它，否則指 target 本身。"""
    from pathlib import Path
    path = Path(target)
    try:
        raw = aos_home.read_json(path) if path.suffix == ".json" else None
    except (aos_home.HomeError, OSError, ValueError):
        return str(path)
    value = raw.get("stderr") if isinstance(raw, dict) else None
    if isinstance(value, dict) and "$opt" in value:
        value = value.get("$val")
    if isinstance(value, str):
        return os.path.abspath(path.parent / value)
    return str(path)  # advice-r1（astra 必修 4）：沒有字面 stderr 就指 target 本身


def ls_data(home, snapshot):
    home = os.path.abspath(home)
    info = load_info(home)
    code, message = health(home, snapshot=snapshot, info=info)
    marks = agent_marks(snapshot)
    if code == "ok":
        # fix-r5：kernel 正常時再看 agent 的暫停／重試，別印一個樂觀的 ok。
        code, message = agents_health(marks) or (code, message)
    daemon = snapshot["daemon"]
    kcpu = snapshot["kernel_cpu"]
    slots = snapshot["cpus"] or {}
    names = dict.fromkeys([*info["cpus"], *slots])
    if kcpu["name"]:
        names[kcpu["name"]] = None
    cpus = []
    for name in names:
        slot = slots.get(name) or {}
        child = daemon["children"].get(name)
        cpus.append({
            "name": name, "pool": info["cpus"].get(name, {}).get("pool"),
            "kernel": name == kcpu["name"], "busy": bool(slot.get("req")),
            "proc": slot.get("proc") if slot.get("req") else None, "req": slot.get("req"),
            "discard": bool(slot.get("discard")),
            # fix-r5：daemon 被 KILL 時孩子表不會更新，這時不給狀態（null）。
            "child": (child["state"] if child else "missing") if daemon["alive"] else None})
    procs = []
    for name, proc in (snapshot["procs"] or {}).items():
        mark = marks.get(name)
        proc = proc if isinstance(proc, dict) else {}
        # astra 必修 2、3：帳本缺鍵或型別不對時正規化成 cli-ls.md 表上寫的型別，不原樣透傳。
        status = proc.get("status") if isinstance(proc.get("status"), str) else "unknown"
        target = proc.get("target") if isinstance(proc.get("target"), str) else None
        procs.append({
            "name": name, "once": bool(proc.get("once")), "pool": _text(proc.get("pool")),
            "status": status, "runs": _count(proc.get("runs")), "fails": _count(proc.get("fails")),
            "pending": bool(proc.get("pending")), "target": target,
            "mark": {"code": mark[0], "text": mark[1]} if mark else None,
            "look": stderr_hint(target) if status == "bad" and target else None})
    queue = list(snapshot["queue"] or [])
    by_status = {}
    for proc in procs:
        by_status[proc["status"]] = by_status.get(proc["status"], 0) + 1
    work = [c for c in cpus if not c["kernel"]]
    busy = sum(c["busy"] for c in work)
    current = kcpu["current"]
    return {
        "_metainfo": dict(META),
        "health": {"code": code, "message": message},
        "kernel": {
            "home": home, "chain": snapshot["chain"], "phase": snapshot["phase"],
            "last_seq": snapshot["last_seq"],
            "daemon": {"home": os.path.abspath(info.get("daemon") or aos_daemon.daemon_home()),
                       "alive": bool(daemon["alive"])},
            "cpu": {"name": kcpu["name"], "current": current.get("name") if isinstance(current, dict) else None,
                    "requests": kcpu["requests"]},
            "settings": {key: info.get(key, DEFAULTS[key]) for key in SETTINGS}},
        "cpus": cpus, "procs": procs, "queue": queue,
        "counts": {"cpus": {"total": len(work), "busy": busy, "idle": len(work) - busy},
                   "procs": {"total": len(procs), "repeat": sum(not p["once"] for p in procs),
                             "once": sum(p["once"] for p in procs), "status": by_status},
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


def _pool_label(pool):
    """null＝info 裡沒有這顆（`?`）；空字串印成 `""`，跟字面 `-` 分開。"""
    return "?" if pool is None else '""' if pool == "" else pool


def render(data, verbose=False):
    k, counts = data["kernel"], data["counts"]
    phase = k["phase"] or "沒 boot 過"
    lines = ["health " + data["health"]["message"],
             "kernel  %s  seq %s  daemon %s  tick %sms" % (
                 phase, "-" if k["last_seq"] is None else k["last_seq"],
                 "alive" if k["daemon"]["alive"] else "dead", k["settings"]["tick_ms"])]
    if verbose:
        lines += ["  K       " + k["home"], "  D       " + k["daemon"]["home"],
                  "  chain   " + (k["chain"] or "-"),
                  "  kcpu    %s  current %s  requests %s" % (
                      k["cpu"]["name"] or "-", k["cpu"]["current"] or "-", k["cpu"]["requests"])]
    else:
        lines.append("  kcpu %s  %s  requests %s" % (
            k["cpu"]["name"] or "-", "正在跑一格" if k["cpu"]["current"] else "沒在跑", k["cpu"]["requests"]))
    c = counts["cpus"]
    head = "cpu     %d 顆：忙 %d、閒 %d%s" % (len(data["cpus"]), c["busy"], c["idle"],
                                          "、kernel %d" % (len(data["cpus"]) - c["total"]) if len(data["cpus"]) > c["total"] else "")
    if not k["daemon"]["alive"]:
        head += "（daemon 沒在跑，孩子狀態不明）"
    lines.append(head)
    order = list(dict.fromkeys(cpu["pool"] for cpu in data["cpus"]))  # 用原值分組（astra 必修 6）
    rows = []
    for pool in order:
        for i, cpu in enumerate(x for x in data["cpus"] if x["pool"] == pool):
            work = "tick" if cpu["kernel"] else ("忙" + ("（rm）" if cpu["discard"] else "")) if cpu["busy"] else "閒"
            proc = cpu["proc"] or "-"
            rows.append([_pool_label(pool) if i == 0 else "", cpu["name"], work,
                         proc if verbose else _cut(proc, NAME_WIDTH), cpu["child"] or "-"])
    if rows:
        lines += _table(["池", "cpu", "工作", "行程", "daemon"], rows)
    p = counts["procs"]
    head = "proc    %d 個" % p["total"]
    if p["total"]:
        head += "（反覆 %d、once %d）：%s" % (p["repeat"], p["once"], "、".join(
            "%s %d" % (status, n) for status, n in sorted(p["status"].items(), key=lambda kv: str(kv[0]))))
    lines.append(head)
    rows = [[proc["name"] if verbose else _cut(proc["name"], NAME_WIDTH), "once" if proc["once"] else "反覆",
             proc["status"] or "-", proc["runs"], proc["fails"], "等" if proc["pending"] else "-",
             proc["mark"]["text"] if proc["mark"] else ""] for proc in data["procs"]]
    if rows:
        lines += _table(["行程", "種類", "狀態", "runs", "fails", "回音", "備註"], rows, right=(3, 4))
    for proc in data["procs"]:
        if proc["look"]:
            lines.append("  %s 壞了，看 %s" % (proc["name"], proc["look"]))
        if verbose and proc["target"]:
            lines.append("  %s  target %s" % (proc["name"], proc["target"]))
    queue = data["queue"]
    shown = queue if verbose else [_cut(n, NAME_WIDTH) for n in queue[:QUEUE_SHOW]]
    more = "" if verbose or len(queue) <= QUEUE_SHOW else " …還有 %d 個" % (len(queue) - QUEUE_SHOW)
    lines.append("queue   " + ("%d：%s%s" % (len(queue), " ".join(shown), more) if queue else "-"))
    return "\n".join(lines)
