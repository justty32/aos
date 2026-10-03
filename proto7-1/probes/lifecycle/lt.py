"""lifecycle 探針的任務腳本。用法：python3 lt.py <模式> [參數...]

每個模式都把事件寫一行到 $AOS7_NODE/<模式>.jsonl（{"ev", "tid", "round", ...}），讓 probe.py 讀。
"""
import json
import os
import signal
import sys
import time

TASK = os.environ.get("AOS7_TASK", "")
NODE = os.environ.get("AOS7_NODE", "")
TID = os.environ.get("AOS7_TID", "")


def rj(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def wj(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def log(_file, **kw):
    kw.setdefault("tid", TID)
    kw.setdefault("round", node_round())
    kw["t"] = time.time()
    with open(os.path.join(NODE, _file + ".jsonl"), "a") as f:
        f.write(json.dumps(kw) + "\n")


def node_round():
    return (rj(os.path.join(NODE, ".aos", "round.json"), {}) or {}).get("round")


def birth():
    return rj(os.path.join(TASK, "birth.json"), {}) or {}


def wait_tock(last, poll=0.01):
    while True:
        t = rj(os.path.join(TASK, "tock.json"))
        if isinstance(t, dict) and isinstance(t.get("round"), int) and t["round"] > last:
            return t["round"]
        time.sleep(poll)


# ---------- (a) 失敗重試 ----------

def flaky_self(n, m, fails):
    """keep 任務自己數：狀態放 node 的 flaky_self.json。太早被起就在程序裡等 tock。"""
    sp = os.path.join(NODE, "flaky_self.json")
    st = rj(sp, {"attempts": 0, "next_round": 0, "done": False})
    b = birth()
    if st.get("done"):
        log("flaky_self", ev="done-skip", birth_round=b.get("round"))
        return 0
    last = b.get("round", 0) - 1
    waited = 0
    while last + 1 < st["next_round"]:   # 還沒到重試的回合：程序活著空等 tock（keep 才不會再起一個）
        last = wait_tock(last)
        waited += 1
    st["attempts"] += 1
    rnd = last + 1                        # 邏輯上的「這回合」（實際落在 tock 與下個 tick 之間）
    if st["attempts"] <= fails and st["attempts"] < m:
        st["next_round"] = rnd + n
        wj(sp, st)
        log("flaky_self", ev="fail", logical=rnd, attempt=st["attempts"], waited_tocks=waited, birth_round=b.get("round"))
        return 1
    st["done"] = True
    wj(sp, st)
    ok = st["attempts"] > fails
    log("flaky_self", ev="ok" if ok else "give-up", logical=rnd, attempt=st["attempts"], waited_tocks=waited, birth_round=b.get("round"))
    return 0 if ok else 1


def job(fails):
    """只由 spawn 起：第 1..fails 次失敗（rc=1），之後成功。次數放 node 的 job_count.json。"""
    p = os.path.join(NODE, "job_count.json")
    c = (rj(p, {}) or {}).get("n", 0) + 1
    wj(p, {"n": c})
    time.sleep(0.02)
    log("job", ev="run", n=c, birth_round=birth().get("round"))
    return 1 if c <= fails else 0


def sup(n, m, job_argv_json):
    """keep 任務當小 kernel：每個 tock 讀自己 node 的 rounds.jsonl，看到 job-* 以 code≠0 結束，
    就排在「結束那回合＋n」重試（寫 spawn/），最多 m 次。狀態放 $AOS7_TASK/sup.json。"""
    job_argv = json.loads(job_argv_json)
    sp = os.path.join(TASK, "sup.json")
    st = rj(sp, {"seen_lines": 0, "attempts": 1, "pending": None, "done": False, "events": []})
    last = birth().get("round", 0) - 1
    rpath = os.path.join(NODE, ".aos", "rounds.jsonl")
    while True:
        last = wait_tock(last)
        lines = []
        try:
            with open(rpath, encoding="utf-8") as f:
                lines = [json.loads(x) for x in f if x.strip()]
        except (OSError, ValueError):
            pass
        for summ in lines[st["seen_lines"]:]:
            for e in summ.get("ended", []):
                if not e["tid"].startswith("job-"):        # rounds.jsonl 的 ended 沒有 name，只能拆 tid
                    continue
                if e.get("code") == 0:
                    st["done"] = True
                    st["events"].append({"ev": "job-ok", "tid": e["tid"], "seen_round": summ["round"]})
                elif st["attempts"] < m:
                    st["pending"] = summ["round"] + n
                    st["events"].append({"ev": "job-fail", "tid": e["tid"], "code": e.get("code"),
                                         "seen_round": summ["round"], "retry_at": st["pending"]})
                else:
                    st["done"] = True
                    st["events"].append({"ev": "give-up", "tid": e["tid"], "seen_round": summ["round"]})
        st["seen_lines"] = len(lines)
        # tock 第 last 回合剛結束；下一個 tick 是 last+1 回合。要在 pending 回合起 → 在 tock(pending-1) 寫 spawn
        if st["pending"] is not None and last + 1 >= st["pending"]:
            st["attempts"] += 1
            wj(os.path.join(NODE, ".aos", "spawn", "sup-job-%d.json" % st["attempts"]),
               {"name": "job", "argv": job_argv})
            st["events"].append({"ev": "spawn", "attempt": st["attempts"], "at_tock": last})
            st["pending"] = None
        wj(sp, st)


# ---------- (b) 自我 restart ----------

def phoenix(gens):
    b = birth()
    prev = b.get("restart_of")
    gen = 0
    if prev:
        ps = rj(os.path.join(os.path.dirname(TASK), prev, "ph.json"), {}) or {}
        gen = ps.get("gen", -1) + 1
    wj(os.path.join(TASK, "ph.json"), {"gen": gen})
    log("phoenix", ev="start", gen=gen, restart_of=prev, birth_round=b.get("round"))

    def term(*_):
        log("phoenix", ev="term", gen=gen)
        sys.exit(0)
    signal.signal(signal.SIGTERM, term)
    last = b.get("round", 0) - 1
    seen = 0
    asked = False
    while True:
        last = wait_tock(last)
        seen += 1
        log("phoenix", ev="tock", gen=gen, tock=last)
        if seen == 2 and gen < gens and not asked:
            wj(os.path.join(TASK, "ctl.json"), {"op": "restart", "by": TID, "why": "self restart gen %d" % gen})
            log("phoenix", ev="ctl-written", gen=gen, tock=last)
            asked = True


# ---------- (c) 別再起我 ----------

def quit_rc0():
    log("quit", ev="start", how="rc0")
    return 0


def quit_marker():
    mk = os.path.join(NODE, "quit_marker.json")
    if os.path.exists(mk):
        log("quit", ev="start-skip", how="marker")
        return 0
    log("quit", ev="start", how="marker")
    wj(mk, {"by": TID})
    return 0


def quit_edit(target_round, gap):
    """等到 tock target_round，把自己從 tasks.json 拿掉（讀—改—寫；中間隔 gap 秒，像 kernel 想一下再寫）。"""
    b = birth()
    log("quit", ev="start", how="edit", name=b.get("name"))
    last = b.get("round", 0) - 1
    while last < target_round:
        last = wait_tock(last)
    p = os.path.join(NODE, ".aos", "tasks.json")
    t = rj(p, {})
    t["tasks"] = [i for i in t.get("tasks", []) if i.get("name") != b.get("name")]
    time.sleep(gap)
    wj(p, t)
    log("quit", ev="edited", how="edit", name=b.get("name"), tock=last)
    return 0


def quit_selfkill():
    b = birth()
    log("quit", ev="start", how="selfkill")
    last = wait_tock(b.get("round", 0) - 1)
    wj(os.path.join(TASK, "ctl.json"), {"op": "kill", "by": TID, "why": "please stop me"})
    log("quit", ev="ctl-written", how="selfkill", tock=last)
    while True:
        time.sleep(0.05)


def main():
    mode, args = sys.argv[1], sys.argv[2:]
    if mode == "flaky_self":
        return flaky_self(int(args[0]), int(args[1]), int(args[2]))
    if mode == "job":
        return job(int(args[0]))
    if mode == "sup":
        return sup(int(args[0]), int(args[1]), args[2])
    if mode == "phoenix":
        return phoenix(int(args[0]))
    if mode == "quit_rc0":
        return quit_rc0()
    if mode == "quit_marker":
        return quit_marker()
    if mode == "quit_edit":
        return quit_edit(int(args[0]), float(args[1]))
    if mode == "quit_selfkill":
        return quit_selfkill()
    if mode == "die":
        sys.exit(int(args[0]))
    return 2


if __name__ == "__main__":
    sys.exit(main())
