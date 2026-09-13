#!/usr/bin/env python3
"""aos-kernel 單顆 cpu 的排程、waiting 與退出碼收尾。"""
import json
import os

from aos_kernel import IDLE_INST


def schedule(h, cfg, st, ready, notes, now):
    present = h.pids()
    on_cpu = {c["pid"] for c in st["cpus"].values() if c}
    waiting = st.setdefault("waiting", {})
    waiting = {pid: runs for pid, runs in waiting.items()
               if pid in present and isinstance(runs, int) and runs > 0}
    st["waiting"] = waiting
    queue = [p for p in st["queue"] if p in present and p not in on_cpu]
    for p in present:
        if p not in queue and p not in on_cpu:
            queue.append(p)
    for n in range(cfg["ncpu"]):
        if n in ready:
            _one_cpu(h, cfg, st, queue, notes, now, n, ready)
    st["queue"] = queue


def _one_cpu(h, cfg, st, queue, notes, now, n, ready):
    cur = st["cpus"].get(str(n))
    ent = ready[n]
    runs_now = ent.get("runs", 0)
    if cur and runs_now < cur.get("seen_runs", cur.get("runs_at", 0)):
        cur["runs_at"] = runs_now
        cur["seen_runs"] = runs_now
        for field in ("waiting", "wait_runs", "bad_runs", "bad_exit", "aos_ticks"):
            cur.pop(field, None)
    if cur is None:
        if queue:
            _take(h, st, queue, notes, now, n, runs_now)
        return

    ran = runs_now - cur.get("runs_at", 0)
    new_runs = max(0, runs_now - cur.get("seen_runs", cur.get("runs_at", 0)))
    if (cfg["done_exit"] != 0 and ent.get("last_kind") == "child"
            and ent.get("last_exit") == cfg["done_exit"] and ran >= 2):
        _finish(h, st, notes, n, cur["pid"])
        return

    if new_runs:
        cur["seen_runs"] = runs_now
        _observe_exit(cfg, cur, ent, new_runs)

    if ent.get("last_kind") == "aos" and ran >= 2:
        cur["aos_ticks"] = cur.get("aos_ticks", 0) + 1
    else:
        cur["aos_ticks"] = 0
    if cur["aos_ticks"] >= 2:
        _reject_running(h, st, notes, n, cur["pid"],
                        "cpu%d 上連續回 125：aos-exec 自己失敗；原因跑 "
                        "aos-exec %s --stderr - 看"
                        % (n, os.path.join(h.bad, "%s.json" % cur["pid"])))
        return

    if cfg["bad_after"] and cur.get("bad_runs", 0) >= cfg["bad_after"]:
        count = cur["bad_runs"]
        code = cur.get("bad_exit")
        _reject_running(h, st, notes, n, cur["pid"],
                        "cpu%d 上連續 %d 次退 %s" % (n, count, code))
        return
    if cur.get("waiting") and ran >= 1 and queue:
        _swap(h, st, queue, notes, now, n, runs_now, cur["pid"])
        return
    if ran >= cfg["quantum"] and queue:
        _swap(h, st, queue, notes, now, n, runs_now, cur["pid"])


def _observe_exit(cfg, cur, ent, new_runs):
    kind = ent.get("last_kind")
    code = ent.get("last_exit")
    if kind == "child" and code == cfg["wait_exit"]:
        cur["waiting"] = True
        cur["wait_runs"] = cur.get("wait_runs", 0) + new_runs
    else:
        cur.pop("waiting", None)
        cur.pop("wait_runs", None)

    excluded = (0, cfg["done_exit"], cfg["wait_exit"], 125)
    if kind == "child" and code not in excluded:
        cur["bad_runs"] = cur.get("bad_runs", 0) + new_runs
        cur["bad_exit"] = code
    else:
        cur.pop("bad_runs", None)
        cur.pop("bad_exit", None)


def _take(h, st, queue, notes, now, n, runs_now):
    """空的 cpu 上人：直接 rename 過去。"""
    nxt = queue[0]
    try:
        os.replace(h.proc(nxt), h.cpu(n))
    except OSError as e:
        notes.append("cpu%d 上 %s 失敗：%s" % (n, nxt, e))
        return
    queue.pop(0)
    cur = {"pid": nxt, "since": now, "runs_at": runs_now, "seen_runs": runs_now}
    wait_runs = st.setdefault("waiting", {}).pop(nxt, None)
    if wait_runs:
        cur.update({"waiting": True, "wait_runs": wait_runs})
    st["cpus"][str(n)] = cur
    notes.append("cpu%d 上 %s" % (n, nxt))


def _swap(h, st, queue, notes, now, n, runs_now, old):
    """跑滿時間片或正在等待：舊的排尾巴，新的原子蓋上 cpu。"""
    cur = st["cpus"][str(n)]
    nxt = queue[0]
    try:
        os.link(h.cpu(n), h.proc(old))
    except OSError as e:
        notes.append("cpu%d 換不了（舊的搬不回去）：%s" % (n, e))
        return
    try:
        os.replace(h.proc(nxt), h.cpu(n))
    except OSError as e:
        os.unlink(h.proc(old))
        notes.append("cpu%d 換不了（新的搬不上去）：%s" % (n, e))
        return
    queue.pop(0)
    queue.append(old)
    waiting = st.setdefault("waiting", {})
    if cur.get("waiting"):
        waiting[old] = cur.get("wait_runs", 0)
    else:
        waiting.pop(old, None)
    new_cur = {"pid": nxt, "since": now, "runs_at": runs_now, "seen_runs": runs_now}
    wait_runs = waiting.pop(nxt, None)
    if wait_runs:
        new_cur.update({"waiting": True, "wait_runs": wait_runs})
    st["cpus"][str(n)] = new_cur
    notes.append("cpu%d 換人 %s→%s%s" %
                 (n, old, nxt, "（%s 在等）" % old if cur.get("waiting") else ""))


def _finish(h, st, notes, n, pid):
    """保留退出碼表示做完：先留 done 名字，再用 idle 原子蓋過 cpu。"""
    if _park(h, h.done, n, pid, notes, "收"):
        st["cpus"][str(n)] = None
        st.setdefault("waiting", {}).pop(pid, None)
        notes.append("cpu%d 上 %s 做完了，收進 procs/done/" % (n, pid))


def _reject_running(h, st, notes, n, pid, reason):
    """退件：先留 bad 名字，再用 idle 原子蓋過 cpu。"""
    if _park(h, h.bad, n, pid, notes, "退"):
        st["cpus"][str(n)] = None
        st.setdefault("waiting", {}).pop(pid, None)
        notes.append("退件 %s（%s）" % (pid, reason))


def _park(h, dst_dir, n, pid, notes, verb):
    tmp = h.cpu(n) + ".tmp"
    dst = os.path.join(dst_dir, "%s.json" % pid)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(IDLE_INST, f, ensure_ascii=False, indent=1)
        os.makedirs(dst_dir, exist_ok=True)
        if os.path.exists(dst):
            os.unlink(dst)
        os.link(h.cpu(n), dst)
    except OSError as e:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        notes.append("cpu%d %s不了 %s：%s" % (n, verb, pid, e))
        return False
    try:
        os.replace(tmp, h.cpu(n))
    except OSError as e:
        os.unlink(dst)
        notes.append("cpu%d %s不了 %s（idle 換不上去）：%s" % (n, verb, pid, e))
        return False
    return True
