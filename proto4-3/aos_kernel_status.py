#!/usr/bin/env python3
"""`aos-kernel ls` 的人類可讀狀態輸出。"""
import os
import time

import aos_home


def show(h, cfg, st, pid_key):
    daemon_home, daemon_state = _daemon_state()
    daemon_pid = daemon_state.get("pid") if daemon_state else None
    if daemon_home is None:
        print("找不到 daemon 的家（AOS_DAEMON_HOME 沒設？）")
    elif not isinstance(daemon_pid, int):
        print("daemon 沒在跑（正常收工過）")
    elif aos_home.alive(daemon_pid):
        print("daemon alive pid=%d" % daemon_pid)
    else:
        print("daemon dead（pid %d 不在了）" % daemon_pid)
    runs = daemon_state.get("runs", {}) if daemon_state else {}
    now = time.time()
    print("家 %s  ncpu=%d interval=%dms timeout=%dms quantum=%d "
          "done_exit=%d wait_exit=%d bad_after=%d"
          % (h.dir, cfg["ncpu"], cfg["interval_ms"], cfg["timeout_ms"], cfg["quantum"],
             cfg["done_exit"], cfg["wait_exit"], cfg["bad_after"]))
    proc_width = max(4, len("PROC"), *(len(str(cur.get("pid")))
                     for cur in st["cpus"].values() if isinstance(cur, dict)))
    columns = (("CPU", 4), ("PROC", proc_width), ("ON", 9), ("RUNS", 5),
               ("LAST_EXIT", 10), ("CPU_STATE", 10))
    row_format = " ".join("%%-%ds" % width for _, width in columns) + " %s"
    print(row_format % (*[name for name, _ in columns], "WAIT"))
    for n in range(cfg["ncpu"]):
        cur = st["cpus"].get(str(n))
        ent = runs.get(os.path.realpath(h.cpu(n)))
        state = ent.get("state", "?") if ent else "沒插上"
        got = ent.get("runs", 0) - cur.get("runs_at", 0) if ent and cur else None
        shown_runs = "-" if got is None else str(got)
        last_exit = "-"
        if ent and got:
            if ent.get("last_kind") == "aos":
                last_exit = "125(aos)"
            elif ent.get("last_exit") is not None:
                last_exit = str(ent.get("last_exit"))
        wait = "-"
        if cur and cur.get("waiting"):
            state = "waiting"
            wait = "等了 %d 回合" % cur.get("wait_runs", 0)
        if cur:
            print(row_format % (n, cur.get("pid"), "%.1fs" % (now - cur.get("since", now)),
                                shown_runs, last_exit, state, wait))
        else:
            print(row_format % (n, "idle", "-", "-", last_exit, state, wait))
    waiting = st.get("waiting", {})
    shown = ["%s (waiting，等了 %d 回合)" % (pid, waiting[pid])
             if pid in waiting else pid for pid in st["queue"]]
    print("佇列（%d 個）：%s" % (len(shown), " ".join(shown) if shown else "沒人在等"))
    _show_retired(h, pid_key)
    _show_modules(h, cfg)


def _daemon_state():
    path = os.environ.get("AOS_DAEMON_HOME")
    if not path or not os.path.isdir(path):
        return None, None
    state = aos_home.Home(path).state()
    return path, state if isinstance(state, dict) else None


def _show_retired(h, pid_key):
    bad = sorted(n for n in os.listdir(h.bad)
                 if os.path.isfile(os.path.join(h.bad, n))) if os.path.isdir(h.bad) else []
    if bad:
        reason = None
        try:
            with open(h.logf, encoding="utf-8") as f:
                for line in reversed(f.readlines()):
                    at = line.find("退件")
                    if at >= 0:
                        reason = line[at:].strip()
                        break
        except OSError:
            pass
        print("bad: %d%s" % (len(bad), "（最近：%s）" % reason if reason else ""))
    done = []
    if os.path.isdir(h.done):
        done = [n[:-5] for n in os.listdir(h.done)
                if n.endswith(".json") and os.path.isfile(os.path.join(h.done, n))]
    if done:
        print("done: %s" % ", ".join(sorted(done, key=pid_key)))


def _show_modules(h, cfg):
    from aos_kernel_module import load_modules
    modules = load_modules(cfg)
    for note in modules.notes:
        print(note)
    for module in modules:
        hook = getattr(module, "status", None)
        if hook is None:
            continue
        try:
            line = hook(h, cfg)
            if line is not None:
                print(line)
        except BaseException as exc:
            print("module %s 壞了：%s" % (module.NAME, str(exc).replace("\n", " ")))
